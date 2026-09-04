// idr_edge — edge-deployable dead-reckoning engine (SIH26168 deliverable (b)).
//
// The problem statement asks for TWO things: a mobile application AND an
// "Edge deployable software engine" that works with "any other external IMU
// sensors data", at "higher update rates ... (around 200Hz)". This binary is
// that engine: a standalone CLI over the same nav:: core the phone uses, with
// a declarative column mapping so it ingests ANY IMU CSV, not just ours.
//
//   idr_edge --input <imu.csv> --map <cols.json> [--rate <hz>] [--out <traj.csv>] [--bench]
//
// No third-party dependencies. C++17. Minimal JSON reader is inline below.

#include "nav/aiding.h"
#include "nav/engine.h"
#include "nav/graphpf.h"
#include "nav/inekf.h"
#include "nav/inference.h"
#include "nav/leansolver.h"
#include "nav/math.h"
#include "nav/metrics.h"
#include "nav/preprocess.h"
#include "nav/types.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <psapi.h>
#if defined(_MSC_VER)
#pragma comment(lib, "psapi.lib")
#endif
#else
#include <sys/resource.h>
#endif

namespace {

const double kNaN = std::numeric_limits<double>::quiet_NaN();

// ---------------------------------------------------------------------------
// Minimal JSON reader (objects, arrays, strings, numbers, true/false/null).
// Enough for a column-mapping file; deliberately not a general JSON library.
// ---------------------------------------------------------------------------
namespace mini {

struct Value;
using Object = std::map<std::string, Value>;
using Array = std::vector<Value>;

struct Value {
  enum class Type { Null, Bool, Number, String, Array, Object };
  Type type = Type::Null;
  bool b = false;
  double num = 0;
  std::string str;
  Array arr;
  Object obj;

  const Value* find(const std::string& k) const {
    if (type != Type::Object) return nullptr;
    const auto it = obj.find(k);
    return it == obj.end() ? nullptr : &it->second;
  }
  bool isNum() const { return type == Type::Number; }
  bool isStr() const { return type == Type::String; }
  double numberOr(double d) const { return type == Type::Number ? num : d; }
  std::string stringOr(const std::string& d) const {
    return type == Type::String ? str : d;
  }
  bool boolOr(bool d) const { return type == Type::Bool ? b : d; }
};

class Parser {
 public:
  Parser(const std::string& s) : s_(s) {}

  bool parse(Value& out, std::string& err) {
    skip();
    if (!value(out, err)) return false;
    skip();
    if (i_ != s_.size()) {
      err = "trailing characters at offset " + std::to_string(i_);
      return false;
    }
    return true;
  }

 private:
  const std::string& s_;
  std::size_t i_ = 0;

  void skip() {
    while (i_ < s_.size()) {
      const char c = s_[i_];
      if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
        ++i_;
      } else if (c == '/' && i_ + 1 < s_.size() && s_[i_ + 1] == '/') {
        while (i_ < s_.size() && s_[i_] != '\n') ++i_;
      } else {
        break;
      }
    }
  }

  bool lit(const char* text) {
    const std::size_t n = std::strlen(text);
    if (s_.compare(i_, n, text) != 0) return false;
    i_ += n;
    return true;
  }

  bool value(Value& v, std::string& err) {
    skip();
    if (i_ >= s_.size()) {
      err = "unexpected end of input";
      return false;
    }
    const char c = s_[i_];
    if (c == '{') return object(v, err);
    if (c == '[') return array(v, err);
    if (c == '"') {
      v.type = Value::Type::String;
      return string(v.str, err);
    }
    if (lit("true")) {
      v.type = Value::Type::Bool;
      v.b = true;
      return true;
    }
    if (lit("false")) {
      v.type = Value::Type::Bool;
      v.b = false;
      return true;
    }
    if (lit("null")) {
      v.type = Value::Type::Null;
      return true;
    }
    return number(v, err);
  }

  bool object(Value& v, std::string& err) {
    v.type = Value::Type::Object;
    ++i_; // '{'
    skip();
    if (i_ < s_.size() && s_[i_] == '}') {
      ++i_;
      return true;
    }
    for (;;) {
      skip();
      std::string key;
      if (i_ >= s_.size() || s_[i_] != '"') {
        err = "expected object key at offset " + std::to_string(i_);
        return false;
      }
      if (!string(key, err)) return false;
      skip();
      if (i_ >= s_.size() || s_[i_] != ':') {
        err = "expected ':' after key '" + key + "'";
        return false;
      }
      ++i_;
      Value child;
      if (!value(child, err)) return false;
      v.obj[key] = child;
      skip();
      if (i_ < s_.size() && s_[i_] == ',') {
        ++i_;
        continue;
      }
      if (i_ < s_.size() && s_[i_] == '}') {
        ++i_;
        return true;
      }
      err = "expected ',' or '}' at offset " + std::to_string(i_);
      return false;
    }
  }

  bool array(Value& v, std::string& err) {
    v.type = Value::Type::Array;
    ++i_; // '['
    skip();
    if (i_ < s_.size() && s_[i_] == ']') {
      ++i_;
      return true;
    }
    for (;;) {
      Value child;
      if (!value(child, err)) return false;
      v.arr.push_back(child);
      skip();
      if (i_ < s_.size() && s_[i_] == ',') {
        ++i_;
        continue;
      }
      if (i_ < s_.size() && s_[i_] == ']') {
        ++i_;
        return true;
      }
      err = "expected ',' or ']' at offset " + std::to_string(i_);
      return false;
    }
  }

  bool string(std::string& out, std::string& err) {
    ++i_; // opening quote
    out.clear();
    while (i_ < s_.size()) {
      const char c = s_[i_++];
      if (c == '"') return true;
      if (c != '\\') {
        out.push_back(c);
        continue;
      }
      if (i_ >= s_.size()) break;
      const char e = s_[i_++];
      switch (e) {
        case 'n': out.push_back('\n'); break;
        case 't': out.push_back('\t'); break;
        case 'r': out.push_back('\r'); break;
        case 'b': out.push_back('\b'); break;
        case 'f': out.push_back('\f'); break;
        case '/': out.push_back('/'); break;
        case '\\': out.push_back('\\'); break;
        case '"': out.push_back('"'); break;
        case 'u': {
          if (i_ + 4 > s_.size()) {
            err = "truncated \\u escape";
            return false;
          }
          const std::string hex = s_.substr(i_, 4);
          i_ += 4;
          const unsigned cp = static_cast<unsigned>(std::strtoul(hex.c_str(), nullptr, 16));
          // Mapping files are ASCII-keyed; keep BMP chars as UTF-8.
          if (cp < 0x80) {
            out.push_back(static_cast<char>(cp));
          } else if (cp < 0x800) {
            out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
          } else {
            out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
          }
          break;
        }
        default:
          err = "bad escape \\";
          err.push_back(e);
          return false;
      }
    }
    err = "unterminated string";
    return false;
  }

  bool number(Value& v, std::string& err) {
    const char* begin = s_.c_str() + i_;
    char* end = nullptr;
    const double d = std::strtod(begin, &end);
    if (end == begin) {
      err = "expected a value at offset " + std::to_string(i_);
      return false;
    }
    i_ += static_cast<std::size_t>(end - begin);
    v.type = Value::Type::Number;
    v.num = d;
    return true;
  }
};

bool parseFile(const std::string& path, Value& out, std::string& err) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    err = "cannot open " + path;
    return false;
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  const std::string text = ss.str();
  Parser p(text);
  return p.parse(out, err);
}

} // namespace mini

// ---------------------------------------------------------------------------
// Column mapping
// ---------------------------------------------------------------------------

// Normalise a header cell: lowercase, drop non-ASCII unit glyphs, collapse
// punctuation to single spaces. "ACCELEROMETER X (m/s²) " -> "accelerometer x m s".
std::string normHeader(const std::string& raw) {
  std::string s;
  s.reserve(raw.size());
  for (unsigned char c : raw) {
    if (c >= 0x80) {
      s.push_back(' ');
    } else if (std::isalnum(c)) {
      s.push_back(static_cast<char>(std::tolower(c)));
    } else if (c == '.' || c == '+') {
      s.push_back(static_cast<char>(c));
    } else {
      s.push_back(' ');
    }
  }
  std::string out;
  bool space = true;
  for (char c : s) {
    if (c == ' ') {
      if (!space) out.push_back(' ');
      space = true;
    } else {
      out.push_back(c);
      space = false;
    }
  }
  while (!out.empty() && out.back() == ' ') out.pop_back();
  return out;
}

struct FieldSpec {
  bool present = false;
  std::string match;   // normalised header substring to look for
  int index = -1;      // explicit 0-based column index (wins over `match`)
  double scale = 1.0;
  double offset = 0.0;
  int resolved = -1;   // column index after binding to a header
};

enum class TimeUnit { Auto, Seconds, Millis, Micros, Nanos };

struct Mapping {
  std::string name = "unnamed";
  std::string description;
  char delimiter = ',';
  bool has_header = true;
  int skip_rows = 0;
  TimeUnit time_unit = TimeUnit::Auto;
  FieldSpec time;
  // Canonical field names understood by nav::ISensorFrame / nav::IGnssFix.
  std::map<std::string, FieldSpec> fields;
  // Optional log metadata defaults.
  std::string vehicle = "motorcycle";
  std::string mount_type = "frame";
  std::string phone_model = "external-imu";
  bool leans = true;
  double imu_hz = 0.0; // 0 = estimate from timestamps
};

const char* const kCanonicalFields[] = {
    "ax", "ay", "az", "gx", "gy", "gz", "mx", "my", "mz",
    "pressure_hpa", "lux", "lat", "lon", "alt", "speed", "bearing",
    "acc_h", "acc_v", "n_sats"};

bool readFieldSpec(const mini::Value& v, FieldSpec& out, std::string& err) {
  out.present = true;
  if (v.type == mini::Value::Type::String) {
    out.match = normHeader(v.str);
    return true;
  }
  if (v.type == mini::Value::Type::Number) {
    out.index = static_cast<int>(v.num);
    return true;
  }
  if (v.type != mini::Value::Type::Object) {
    err = "field spec must be a string, a column index, or an object";
    return false;
  }
  if (const mini::Value* m = v.find("match")) out.match = normHeader(m->stringOr(""));
  if (const mini::Value* m = v.find("column")) out.match = normHeader(m->stringOr(""));
  if (const mini::Value* m = v.find("index")) out.index = static_cast<int>(m->numberOr(-1));
  if (const mini::Value* m = v.find("scale")) out.scale = m->numberOr(1.0);
  if (const mini::Value* m = v.find("offset")) out.offset = m->numberOr(0.0);
  if (out.match.empty() && out.index < 0) {
    err = "field spec has neither \"match\"/\"column\" nor \"index\"";
    return false;
  }
  return true;
}

bool loadMapping(const std::string& path, Mapping& m, std::string& err) {
  mini::Value root;
  if (!mini::parseFile(path, root, err)) return false;
  if (root.type != mini::Value::Type::Object) {
    err = path + ": top level must be a JSON object";
    return false;
  }
  if (const mini::Value* v = root.find("name")) m.name = v->stringOr(m.name);
  if (const mini::Value* v = root.find("description")) m.description = v->stringOr("");
  if (const mini::Value* v = root.find("delimiter")) {
    const std::string d = v->stringOr(",");
    if (!d.empty()) m.delimiter = d == "\\t" ? '\t' : d[0];
  }
  if (const mini::Value* v = root.find("has_header")) m.has_header = v->boolOr(true);
  if (const mini::Value* v = root.find("skip_rows")) m.skip_rows = static_cast<int>(v->numberOr(0));

  const mini::Value* t = root.find("time");
  if (!t) {
    err = path + ": mapping must define \"time\"";
    return false;
  }
  if (!readFieldSpec(*t, m.time, err)) {
    err = path + ": time: " + err;
    return false;
  }
  std::string unit = "auto";
  if (t->type == mini::Value::Type::Object) {
    if (const mini::Value* u = t->find("unit")) unit = u->stringOr("auto");
  }
  if (unit == "s" || unit == "sec" || unit == "seconds") m.time_unit = TimeUnit::Seconds;
  else if (unit == "ms" || unit == "millis") m.time_unit = TimeUnit::Millis;
  else if (unit == "us" || unit == "micros") m.time_unit = TimeUnit::Micros;
  else if (unit == "ns" || unit == "nanos") m.time_unit = TimeUnit::Nanos;
  else if (unit == "auto") m.time_unit = TimeUnit::Auto;
  else {
    err = path + ": unknown time unit \"" + unit + "\"";
    return false;
  }

  const mini::Value* fields = root.find("fields");
  if (!fields) fields = root.find("columns");
  if (!fields || fields->type != mini::Value::Type::Object) {
    err = path + ": mapping must define a \"fields\" object";
    return false;
  }
  for (const auto& kv : fields->obj) {
    bool known = false;
    for (const char* c : kCanonicalFields) {
      if (kv.first == c) known = true;
    }
    if (!known) {
      err = path + ": unknown field \"" + kv.first + "\"";
      return false;
    }
    FieldSpec fs;
    if (!readFieldSpec(kv.second, fs, err)) {
      err = path + ": field " + kv.first + ": " + err;
      return false;
    }
    m.fields[kv.first] = fs;
  }
  const char* const required[] = {"ax", "ay", "az", "gx", "gy", "gz"};
  for (const char* r : required) {
    if (m.fields.find(r) == m.fields.end()) {
      err = path + ": mapping is missing required field \"" + std::string(r) + "\"";
      return false;
    }
  }

  if (const mini::Value* meta = root.find("meta")) {
    if (const mini::Value* v = meta->find("vehicle")) m.vehicle = v->stringOr(m.vehicle);
    if (const mini::Value* v = meta->find("mount_type")) m.mount_type = v->stringOr(m.mount_type);
    if (const mini::Value* v = meta->find("phone_model")) m.phone_model = v->stringOr(m.phone_model);
    if (const mini::Value* v = meta->find("leans")) m.leans = v->boolOr(m.leans);
    if (const mini::Value* v = meta->find("imu_hz")) m.imu_hz = v->numberOr(0.0);
  }
  return true;
}

// ---------------------------------------------------------------------------
// CSV ingestion
// ---------------------------------------------------------------------------

void splitRow(const std::string& line, char delim, std::vector<std::string>& out) {
  out.clear();
  std::string cur;
  bool quoted = false;
  for (std::size_t i = 0; i < line.size(); ++i) {
    const char c = line[i];
    if (quoted) {
      if (c == '"') {
        if (i + 1 < line.size() && line[i + 1] == '"') {
          cur.push_back('"');
          ++i;
        } else {
          quoted = false;
        }
      } else {
        cur.push_back(c);
      }
    } else if (c == '"') {
      quoted = true;
    } else if (c == delim) {
      out.push_back(cur);
      cur.clear();
    } else if (c != '\r') {
      cur.push_back(c);
    }
  }
  out.push_back(cur);
}

double parseCell(const std::string& cell) {
  const char* b = cell.c_str();
  while (*b == ' ' || *b == '\t') ++b;
  if (*b == '\0') return kNaN;
  char* end = nullptr;
  const double d = std::strtod(b, &end);
  if (end == b) return kNaN;
  return d;
}

// Bind every field spec to a concrete column index.
bool bindColumns(Mapping& m, const std::vector<std::string>& header, std::string& err) {
  std::vector<std::string> norm;
  norm.reserve(header.size());
  for (const auto& h : header) norm.push_back(normHeader(h));

  auto bind = [&](FieldSpec& fs, const std::string& name) -> bool {
    if (!fs.present) return true;
    if (fs.index >= 0) {
      fs.resolved = fs.index;
      return true;
    }
    if (!m.has_header) {
      err = "field \"" + name + "\" needs an explicit \"index\" when has_header is false";
      return false;
    }
    // Pass 1: exact normalised equality. Pass 2: substring.
    for (std::size_t i = 0; i < norm.size(); ++i) {
      if (norm[i] == fs.match) {
        fs.resolved = static_cast<int>(i);
        return true;
      }
    }
    for (std::size_t i = 0; i < norm.size(); ++i) {
      if (norm[i].find(fs.match) != std::string::npos) {
        fs.resolved = static_cast<int>(i);
        return true;
      }
    }
    err = "field \"" + name + "\" (match \"" + fs.match + "\") not found in header";
    return false;
  };

  if (!bind(m.time, "time")) return false;
  for (auto& kv : m.fields) {
    if (!bind(kv.second, kv.first)) return false;
  }
  return true;
}

struct LoadResult {
  std::vector<nav::ISensorFrame> imu;
  std::vector<nav::IGnssFix> gnss;
  double hz_est = 0;
  std::size_t rows_read = 0;
  std::size_t rows_skipped = 0;
  std::size_t time_resets = 0;
  std::size_t rows_dropped_session = 0;
  std::string time_unit_used;
  std::map<std::string, std::string> bound; // field -> header cell
};

double medianOf(std::vector<double> v) {
  if (v.empty()) return 0;
  std::sort(v.begin(), v.end());
  return v[v.size() / 2];
}

bool loadCsv(const std::string& path, Mapping& m, std::size_t limit, bool use_gnss,
             bool session_longest, LoadResult& out, std::string& err) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    err = "cannot open " + path;
    return false;
  }
  // Git LFS pointer stubs are ~130 bytes of text, not data. Refuse them loudly.
  in.seekg(0, std::ios::end);
  const std::streamoff bytes = in.tellg();
  in.seekg(0, std::ios::beg);
  if (bytes > 0 && bytes < 1024) {
    std::string head(static_cast<std::size_t>(bytes), '\0');
    in.read(&head[0], bytes);
    in.clear();
    in.seekg(0, std::ios::beg);
    if (head.find("git-lfs") != std::string::npos) {
      err = path + " is a Git LFS pointer stub (" + std::to_string(bytes) +
            " bytes), not data. Run: git lfs pull";
      return false;
    }
  }

  std::string line;
  std::vector<std::string> cells;
  for (int i = 0; i < m.skip_rows; ++i) std::getline(in, line);

  std::vector<std::string> header;
  if (m.has_header) {
    if (!std::getline(in, line)) {
      err = path + ": empty file";
      return false;
    }
    splitRow(line, m.delimiter, header);
  }
  if (!bindColumns(m, header, err)) {
    err = path + ": " + err;
    return false;
  }
  auto headerName = [&](int idx) -> std::string {
    if (idx >= 0 && idx < static_cast<int>(header.size())) return header[idx];
    return "col[" + std::to_string(idx) + "]";
  };
  out.bound["time"] = headerName(m.time.resolved);
  for (const auto& kv : m.fields) out.bound[kv.first] = headerName(kv.second.resolved);

  auto get = [&](const std::vector<std::string>& row, const FieldSpec& fs) -> double {
    if (!fs.present || fs.resolved < 0 || fs.resolved >= static_cast<int>(row.size())) {
      return kNaN;
    }
    const double v = parseCell(row[static_cast<std::size_t>(fs.resolved)]);
    return v * fs.scale + fs.offset;
  };
  auto has = [&](const char* name) {
    return m.fields.find(name) != m.fields.end();
  };
  auto fs = [&](const char* name) -> const FieldSpec& {
    static const FieldSpec empty;
    const auto it = m.fields.find(name);
    return it == m.fields.end() ? empty : it->second;
  };

  // Pass 1: raw rows (time kept in the file's own units).
  struct Row {
    double t;
    double ax, ay, az, gx, gy, gz, mx, my, mz, p, lux;
    double lat, lon, alt, speed, bearing, acc_h, acc_v, sats;
  };
  std::vector<Row> rows;
  rows.reserve(1 << 16);

  while (std::getline(in, line)) {
    if (line.empty()) continue;
    splitRow(line, m.delimiter, cells);
    ++out.rows_read;
    Row r{};
    r.t = get(cells, m.time);
    r.ax = get(cells, fs("ax"));
    r.ay = get(cells, fs("ay"));
    r.az = get(cells, fs("az"));
    r.gx = get(cells, fs("gx"));
    r.gy = get(cells, fs("gy"));
    r.gz = get(cells, fs("gz"));
    if (!std::isfinite(r.t) || !std::isfinite(r.ax) || !std::isfinite(r.ay) ||
        !std::isfinite(r.az) || !std::isfinite(r.gx) || !std::isfinite(r.gy) ||
        !std::isfinite(r.gz)) {
      ++out.rows_skipped;
      continue;
    }
    r.mx = has("mx") ? get(cells, fs("mx")) : 0.0;
    r.my = has("my") ? get(cells, fs("my")) : 0.0;
    r.mz = has("mz") ? get(cells, fs("mz")) : 0.0;
    r.p = has("pressure_hpa") ? get(cells, fs("pressure_hpa")) : 1013.25;
    r.lux = has("lux") ? get(cells, fs("lux")) : 0.0;
    r.lat = has("lat") ? get(cells, fs("lat")) : kNaN;
    r.lon = has("lon") ? get(cells, fs("lon")) : kNaN;
    r.alt = has("alt") ? get(cells, fs("alt")) : kNaN;
    r.speed = has("speed") ? get(cells, fs("speed")) : kNaN;
    r.bearing = has("bearing") ? get(cells, fs("bearing")) : kNaN;
    r.acc_h = has("acc_h") ? get(cells, fs("acc_h")) : kNaN;
    r.acc_v = has("acc_v") ? get(cells, fs("acc_v")) : kNaN;
    r.sats = has("n_sats") ? get(cells, fs("n_sats")) : kNaN;
    rows.push_back(r);
    if (limit > 0 && rows.size() >= limit) break;
  }
  if (rows.size() < 4) {
    err = path + ": only " + std::to_string(rows.size()) + " usable rows";
    return false;
  }

  // Real logs concatenate drives: IO-VNBD S-*.csv restarts TIME SINCE START
  // mid-file. A backward dt makes the estimator meaningless, so count the
  // resets always and, on request, keep only the longest monotonic run.
  std::size_t best_a = 0, best_b = rows.size();
  {
    std::size_t run_a = 0, best_len = 0;
    for (std::size_t i = 1; i <= rows.size(); ++i) {
      const bool broken = i < rows.size() && !(rows[i].t > rows[i - 1].t);
      if (i == rows.size() || broken) {
        if (i - run_a > best_len) {
          best_len = i - run_a;
          best_a = run_a;
          best_b = i;
        }
        if (broken) {
          ++out.time_resets;
          run_a = i;
        }
      }
    }
  }
  if (session_longest && out.time_resets > 0) {
    out.rows_dropped_session = rows.size() - (best_b - best_a);
    rows = std::vector<Row>(rows.begin() + static_cast<std::ptrdiff_t>(best_a),
                            rows.begin() + static_cast<std::ptrdiff_t>(best_b));
    if (rows.size() < 4) {
      err = path + ": longest monotonic session has only " +
            std::to_string(rows.size()) + " rows";
      return false;
    }
  }

  // Time unit. "auto" picks the scale that puts the median step in [1e-4, 1] s.
  double to_ns = 1e9;
  TimeUnit unit = m.time_unit;
  if (unit == TimeUnit::Auto) {
    std::vector<double> dts;
    dts.reserve(std::min<std::size_t>(rows.size() - 1, 4096));
    for (std::size_t i = 1; i < rows.size() && dts.size() < 4096; ++i) {
      const double d = rows[i].t - rows[i - 1].t;
      if (d > 0) dts.push_back(d);
    }
    const double med = medianOf(dts);
    if (med <= 0) unit = TimeUnit::Seconds;
    else if (med < 1.0) unit = TimeUnit::Seconds;
    else if (med < 1e3) unit = TimeUnit::Millis;
    else if (med < 1e6) unit = TimeUnit::Micros;
    else unit = TimeUnit::Nanos;
  }
  switch (unit) {
    case TimeUnit::Seconds: to_ns = 1e9; out.time_unit_used = "s"; break;
    case TimeUnit::Millis: to_ns = 1e6; out.time_unit_used = "ms"; break;
    case TimeUnit::Micros: to_ns = 1e3; out.time_unit_used = "us"; break;
    case TimeUnit::Nanos: to_ns = 1.0; out.time_unit_used = "ns"; break;
    default: break;
  }

  const double t0 = rows.front().t;
  out.imu.reserve(rows.size());
  double last_lat = kNaN, last_lon = kNaN;
  for (const Row& r : rows) {
    nav::ISensorFrame f;
    f.t_ns = static_cast<std::int64_t>((r.t - t0) * to_ns);
    f.ax = r.ax;
    f.ay = r.ay;
    f.az = r.az;
    f.gx = r.gx;
    f.gy = r.gy;
    f.gz = r.gz;
    f.mx = r.mx;
    f.my = r.my;
    f.mz = r.mz;
    f.pressure_hpa = std::isfinite(r.p) ? r.p : 1013.25;
    f.lux = std::isfinite(r.lux) ? r.lux : 0.0;
    out.imu.push_back(f);

    if (!use_gnss) continue;
    if (!std::isfinite(r.lat) || !std::isfinite(r.lon)) continue;
    // Emit one fix per distinct position. IO-VNBD holds each GPS fix across
    // many IMU rows; a fix per row would fake a 10 Hz GNSS receiver.
    const bool moved = !std::isfinite(last_lat) ||
                       std::abs(r.lat - last_lat) > 1e-9 ||
                       std::abs(r.lon - last_lon) > 1e-9;
    if (!moved) continue;
    last_lat = r.lat;
    last_lon = r.lon;
    nav::IGnssFix fix;
    fix.t_ns = out.imu.back().t_ns;
    fix.lat = r.lat;
    fix.lon = r.lon;
    fix.alt = std::isfinite(r.alt) ? r.alt : 0.0;
    fix.speed = std::isfinite(r.speed) ? r.speed : 0.0;
    fix.bearing = std::isfinite(r.bearing) ? r.bearing : 0.0;
    fix.acc_h = std::isfinite(r.acc_h) ? r.acc_h : 5.0;
    fix.acc_v = std::isfinite(r.acc_v) ? r.acc_v : 8.0;
    fix.n_sats = std::isfinite(r.sats) ? static_cast<int>(r.sats) : 0;
    out.gnss.push_back(fix);
  }

  std::vector<double> dt_s;
  dt_s.reserve(std::min<std::size_t>(out.imu.size() - 1, 4096));
  for (std::size_t i = 1; i < out.imu.size() && dt_s.size() < 4096; ++i) {
    const double d = static_cast<double>(out.imu[i].t_ns - out.imu[i - 1].t_ns) / 1e9;
    if (d > 1e-7) dt_s.push_back(d);
  }
  const double med = medianOf(dt_s);
  out.hz_est = med > 0 ? 1.0 / med : 0.0;
  return true;
}

// ---------------------------------------------------------------------------
// Synthetic external-IMU generator (self-contained benchmark input)
// ---------------------------------------------------------------------------

// A coordinated-turn two-wheeler: constant speed, sinusoidal lean, with the
// gyro triad written from the exact kinematics used by nav::solveLean.
std::vector<nav::ISensorFrame> synthesise(double seconds, double hz, double speed_mps) {
  std::vector<nav::ISensorFrame> out;
  const std::int64_t dt_ns = static_cast<std::int64_t>(1e9 / hz);
  const std::size_t n = static_cast<std::size_t>(seconds * hz);
  out.reserve(n);
  nav::Rng32 rng(26168u);
  for (std::size_t i = 0; i < n; ++i) {
    const double t = static_cast<double>(i) / hz;
    // Lean sweeps +-25 deg with a 12 s period; straight sections in between.
    const double phi = 25.0 * nav::kDeg * std::sin(2.0 * nav::kPi * t / 12.0);
    const double psi_dot = (nav::kG * std::tan(phi)) / std::max(1.0, speed_mps);
    nav::ISensorFrame f;
    f.t_ns = static_cast<std::int64_t>(i) * dt_ns;
    f.gx = 0.5 * nav::kDeg * std::cos(2.0 * nav::kPi * t / 12.0) + 0.004 * nav::gauss(rng);
    f.gy = psi_dot * std::sin(phi) + 0.004 * nav::gauss(rng);
    f.gz = psi_dot * std::cos(phi) + 0.004 * nav::gauss(rng);
    f.ax = 0.15 * std::sin(2.0 * nav::kPi * t / 40.0) + 0.05 * nav::gauss(rng);
    f.ay = -speed_mps * psi_dot * std::cos(phi) + 0.05 * nav::gauss(rng);
    f.az = nav::kG / std::cos(phi) + 0.05 * nav::gauss(rng);
    f.mx = 22.0;
    f.my = -3.0;
    f.mz = 41.0;
    f.pressure_hpa = 1013.25;
    f.lux = 120.0;
    out.push_back(f);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Streaming edge engine — the same composition as nav::runEngine's inner loop,
// driven one sample at a time so per-sample latency is measurable.
// ---------------------------------------------------------------------------

struct StreamCfg {
  double hz = 200.0;
  double filter_fc = 8.0;
  bool two_wheeler = true;
  bool use_graph = false;
  int particles = 180;
  nav::Lla origin;
};

class EdgeStream {
 public:
  EdgeStream(const StreamCfg& cfg, const std::vector<nav::IGnssFix>& fixes,
             const nav::IRoadGraph& graph)
      : cfg_(cfg),
        fixes_(fixes),
        graph_(graph),
        filt_(cfg.filter_fc, cfg.hz > 1.0 ? cfg.hz : 50.0),
        odo_(cfg.hz > 1.0 ? cfg.hz : 50.0),
        ekf_(cfg.origin, cfg.two_wheeler),
        pf_(graph, nav::GraphPfConfig{cfg.particles, 1u}),
        light_(nav::createLightCounter()) {
    if (!fixes_.empty()) {
      ekf_.seedFromGnss(fixes_.front());
    } else {
      nav::IGnssFix seed;
      seed.t_ns = 0;
      seed.lat = cfg.origin.lat;
      seed.lon = cfg.origin.lon;
      seed.alt = cfg.origin.alt;
      seed.acc_h = 5;
      seed.acc_v = 8;
      ekf_.seedFromGnss(seed);
    }
    if (cfg_.use_graph) {
      const nav::INavState s0 = ekf_.toState(0);
      pf_.seed(s0.lat, s0.lon, 0);
    }
  }

  nav::INavState step(const nav::ISensorFrame& raw) {
    cal_.observe(raw);
    const nav::ISensorFrame f = filt_.apply(cal_.apply(raw));
    const bool denied = outageAt(f.t_ns, 1500000000LL);
    if (denied) ekf_.markOutage();

    while (gi_ < fixes_.size() && fixes_[gi_].t_ns <= f.t_ns) {
      const std::int64_t d = f.t_ns - fixes_[gi_].t_ns;
      if (d <= 800000000LL) ekf_.updateGnss(fixes_[gi_]);
      ++gi_;
    }
    const nav::IGnssFix* last_fix = gi_ > 0 ? &fixes_[gi_ - 1] : nullptr;

    if (!denied && last_fix) odo_.setSpeed(last_fix->speed);
    const nav::OdoEstimate o = odo_.push(f);
    if (!denied && last_fix) odo_.setSpeed(last_fix->speed);

    ekf_.propagate(f);
    const double dt = last_t_ >= 0 ? static_cast<double>(f.t_ns - last_t_) / 1e9
                                   : 1.0 / cfg_.hz;
    last_t_ = f.t_ns;

    if (!cfg_.two_wheeler) {
      ekf_.lean = 0;
    } else {
      nav::LeanObservation obs;
      obs.gy = f.gy;
      obs.gz = f.gz;
      obs.gx = f.gx;
      obs.speed = o.speed > 0.0 ? o.speed : ekf_.toState(f.t_ns).speed;
      obs.phi0 = ekf_.lean;
      obs.has_phi0 = true;
      ekf_.lean = nav::solveLean(obs).phi;
    }

    nav::INavState st = ekf_.toState(f.t_ns);
    st.mode = denied ? "ins" : "gnss";
    if (!cfg_.use_graph) {
      ++n_;
      if (denied) ++n_denied_;
      return st;
    }

    if (denied) {
      const nav::IGraphEdge* edge = nav::edgeById(graph_, st.edge_id);
      if (!edge) {
        for (const auto& e : graph_.edges) {
          if (e.tunnel) {
            edge = &e;
            break;
          }
        }
      }
      if (edge && edge->light_spacing_m > 0.0) {
        light_ = nav::stepLightCount(light_, f.lux, f.t_ns, edge->light_spacing_m);
      }
      pf_.step(std::max(0.001, dt), st.speed, nav::rad2deg(st.yaw), f.lux, f.pressure_hpa);
      st = pf_.estimate(st);
      ++n_denied_;
    } else {
      const nav::MapProject proj = pf_.mapProject(st.lat, st.lon, nav::rad2deg(st.yaw));
      pf_.seed(proj.lat, proj.lon, nav::rad2deg(st.yaw));
      st.edge_id = proj.edge_id;
      st.mode = "gnss";
    }
    ++n_;
    return st;
  }

  std::size_t denied() const { return n_denied_; }

 private:
  // Streaming equivalent of nav::gnssOutageMask: nearest fix in time, but with
  // a cursor instead of a full scan (identical result for time-sorted fixes).
  bool outageAt(std::int64_t t_ns, std::int64_t gap_ns) {
    if (fixes_.empty()) return true;
    while (oc_ + 1 < fixes_.size() && fixes_[oc_ + 1].t_ns <= t_ns) ++oc_;
    std::int64_t best = std::abs(fixes_[oc_].t_ns - t_ns);
    if (oc_ + 1 < fixes_.size()) {
      best = std::min(best, std::abs(fixes_[oc_ + 1].t_ns - t_ns));
    }
    return best > gap_ns;
  }

  StreamCfg cfg_;
  const std::vector<nav::IGnssFix>& fixes_;
  nav::IRoadGraph graph_;
  nav::SixAxisFilter filt_;
  nav::BiasCalibrator cal_;
  nav::FrequencyDecoupledOdo odo_;
  nav::InvariantEKF ekf_;
  nav::GraphParticleFilter pf_;
  nav::LightCounterState light_;
  std::size_t gi_ = 0;
  std::size_t oc_ = 0;
  std::size_t n_ = 0;
  std::size_t n_denied_ = 0;
  std::int64_t last_t_ = -1;
};

// ---------------------------------------------------------------------------
// Reporting helpers
// ---------------------------------------------------------------------------

double peakRssMb() {
#if defined(_WIN32)
  PROCESS_MEMORY_COUNTERS pmc;
  if (GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc))) {
    return static_cast<double>(pmc.PeakWorkingSetSize) / (1024.0 * 1024.0);
  }
  return -1.0;
#else
  struct rusage ru;
  if (getrusage(RUSAGE_SELF, &ru) == 0) {
#if defined(__APPLE__)
    return static_cast<double>(ru.ru_maxrss) / (1024.0 * 1024.0);
#else
    return static_cast<double>(ru.ru_maxrss) / 1024.0;
#endif
  }
  return -1.0;
#endif
}

double percentile(std::vector<double>& v, double q) {
  if (v.empty()) return 0;
  std::sort(v.begin(), v.end());
  const double pos = q * static_cast<double>(v.size() - 1);
  const std::size_t lo = static_cast<std::size_t>(pos);
  const std::size_t hi = std::min(lo + 1, v.size() - 1);
  const double frac = pos - static_cast<double>(lo);
  return v[lo] + (v[hi] - v[lo]) * frac;
}

void usage() {
  std::cout <<
      "idr_edge - edge-deployable dead-reckoning engine (SIH26168)\n"
      "\n"
      "Usage:\n"
      "  idr_edge --input <imu.csv> --map <cols.json> [options]\n"
      "  idr_edge --synth <seconds> [options]\n"
      "\n"
      "Input:\n"
      "  --input <path>      IMU CSV of any layout (see --map)\n"
      "  --map <path>        JSON column mapping (apps/mappings/*.json)\n"
      "  --synth <seconds>   generate a coordinated-turn IMU stream instead\n"
      "  --limit <n>         use only the first n rows\n"
      "  --no-gnss           ignore lat/lon/speed columns (pure dead reckoning)\n"
      "  --session-longest   keep only the longest monotonic-time run\n"
      "\n"
      "Engine:\n"
      "  --rate <hz>         declared IMU rate (default: median of timestamps)\n"
      "  --resample <hz>     resample the input to <hz> before running\n"
      "  --mode stream|batch stream = per-sample (default); batch = nav::runEngine\n"
      "  --vehicle <name>    car | scooter | motorcycle | bicycle\n"
      "  --graph campus|none built-in demo road graph for the particle filter\n"
      "  --particles <n>     graph particle count (default 180)\n"
      "  --origin lat,lon,alt fallback origin when the input has no GNSS\n"
      "\n"
      "Output:\n"
      "  --out <path>        write the trajectory CSV\n"
      "  --emit-input <path> write the ingested IMU stream back out as a CSV that\n"
      "                      mappings/external_imu_200hz.json can read\n"
      "  --bench             report throughput, latency and peak memory\n"
      "  --repeat <k>        bench: replay the stream k times (default 1)\n"
      "  --quiet             suppress the ingestion summary\n"
      "  --help\n";
}

} // namespace

int main(int argc, char** argv) {
  std::string input, mapping_path, out_path, emit_path, mode = "stream", graph_name = "none";
  std::string vehicle;
  double rate = 0.0, resample_hz = 0.0, synth_s = 0.0;
  std::size_t limit = 0;
  int repeat = 1, particles = 180;
  bool bench = false, quiet = false, use_gnss = true, session_longest = false;
  nav::Lla origin{0, 0, 0};
  bool origin_set = false;

  auto need = [&](int& i, const char* flag) -> std::string {
    if (i + 1 >= argc) {
      std::cerr << "idr_edge: " << flag << " needs a value\n";
      std::exit(2);
    }
    return argv[++i];
  };

  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    if (a == "--help" || a == "-h") {
      usage();
      return 0;
    } else if (a == "--input") input = need(i, "--input");
    else if (a == "--map") mapping_path = need(i, "--map");
    else if (a == "--out") out_path = need(i, "--out");
    else if (a == "--emit-input") emit_path = need(i, "--emit-input");
    else if (a == "--mode") mode = need(i, "--mode");
    else if (a == "--graph") graph_name = need(i, "--graph");
    else if (a == "--vehicle") vehicle = need(i, "--vehicle");
    else if (a == "--rate") rate = std::atof(need(i, "--rate").c_str());
    else if (a == "--resample") resample_hz = std::atof(need(i, "--resample").c_str());
    else if (a == "--synth") synth_s = std::atof(need(i, "--synth").c_str());
    else if (a == "--limit") limit = static_cast<std::size_t>(std::atoll(need(i, "--limit").c_str()));
    else if (a == "--repeat") repeat = std::atoi(need(i, "--repeat").c_str());
    else if (a == "--particles") particles = std::atoi(need(i, "--particles").c_str());
    else if (a == "--bench") bench = true;
    else if (a == "--quiet") quiet = true;
    else if (a == "--no-gnss") use_gnss = false;
    else if (a == "--session-longest") session_longest = true;
    else if (a == "--origin") {
      const std::string v = need(i, "--origin");
      if (std::sscanf(v.c_str(), "%lf,%lf,%lf", &origin.lat, &origin.lon, &origin.alt) < 2) {
        std::cerr << "idr_edge: --origin wants lat,lon[,alt]\n";
        return 2;
      }
      origin_set = true;
    } else {
      std::cerr << "idr_edge: unknown option " << a << " (try --help)\n";
      return 2;
    }
  }

  if (input.empty() && synth_s <= 0.0) {
    usage();
    return 2;
  }
  if (!input.empty() && mapping_path.empty()) {
    std::cerr << "idr_edge: --input needs --map <cols.json>\n";
    return 2;
  }
  if (repeat < 1) repeat = 1;

  Mapping mapping;
  LoadResult data;
  const auto t_load0 = std::chrono::steady_clock::now();

  if (!input.empty()) {
    std::string err;
    if (!loadMapping(mapping_path, mapping, err)) {
      std::cerr << "idr_edge: " << err << "\n";
      return 1;
    }
    if (!loadCsv(input, mapping, limit, use_gnss, session_longest, data, err)) {
      std::cerr << "idr_edge: " << err << "\n";
      return 1;
    }
  } else {
    const double hz = rate > 0.0 ? rate : 200.0;
    data.imu = synthesise(synth_s, hz, 12.0);
    data.rows_read = data.imu.size();
    data.hz_est = hz;
    data.time_unit_used = "ns (synthetic)";
    mapping.name = "synthetic-coordinated-turn";
    mapping.vehicle = "motorcycle";
    mapping.mount_type = "frame";
    mapping.leans = true;
    if (limit > 0 && data.imu.size() > limit) data.imu.resize(limit);
  }
  const auto t_load1 = std::chrono::steady_clock::now();
  const double load_s = std::chrono::duration<double>(t_load1 - t_load0).count();

  if (data.imu.size() < 4) {
    std::cerr << "idr_edge: not enough IMU samples\n";
    return 1;
  }

  double hz = rate > 0.0 ? rate : (data.hz_est > 0.0 ? data.hz_est : 50.0);
  if (resample_hz > 0.0) {
    data.imu = nav::resampleLinear(data.imu, resample_hz);
    hz = resample_hz;
  }

  if (!origin_set) {
    if (!data.gnss.empty()) {
      origin.lat = data.gnss.front().lat;
      origin.lon = data.gnss.front().lon;
      origin.alt = data.gnss.front().alt;
    } else if (graph_name == "campus" || mode == "batch") {
      // nav::runEngine always falls back to the built-in campus graph, so in
      // batch mode that graph's origin IS the engine origin.
      origin = nav::defaultCampusGraph().origin;
    }
  }

  if (!emit_path.empty()) {
    std::ofstream e(emit_path, std::ios::binary);
    if (!e) {
      std::cerr << "idr_edge: cannot write " << emit_path << "\n";
      return 1;
    }
    e << "t_ns,ax,ay,az,gx,gy,gz,mx,my,mz,pressure_hpa,lux\n";
    e << std::fixed << std::setprecision(9);
    for (const nav::ISensorFrame& f : data.imu) {
      e << f.t_ns << ',' << f.ax << ',' << f.ay << ',' << f.az << ','
        << f.gx << ',' << f.gy << ',' << f.gz << ','
        << f.mx << ',' << f.my << ',' << f.mz << ','
        << f.pressure_hpa << ',' << f.lux << '\n';
    }
    if (!quiet) {
      std::cout << "emitted      : " << emit_path << " (" << data.imu.size()
                << " rows)\n";
    }
  }

  const std::string veh = vehicle.empty() ? mapping.vehicle : vehicle;
  const bool two_wheeler = veh != "car";

  if (!quiet) {
    std::cout << "input        : " << (input.empty() ? "<synthetic>" : input) << "\n"
              << "mapping      : " << mapping.name << "\n"
              << "samples      : " << data.imu.size();
    if (data.rows_skipped) std::cout << "  (skipped " << data.rows_skipped << " bad rows)";
    std::cout << "\n";
    std::cout << "duration     : " << std::fixed << std::setprecision(2)
              << static_cast<double>(data.imu.back().t_ns - data.imu.front().t_ns) / 1e9
              << " s\n";
    std::cout << "rate         : " << std::setprecision(2) << hz << " Hz";
    if (rate <= 0.0 && resample_hz <= 0.0) std::cout << " (estimated)";
    std::cout << "\n";
    if (!input.empty()) std::cout << "time unit    : " << data.time_unit_used << "\n";
    if (data.time_resets > 0) {
      std::cout << "time resets  : " << data.time_resets
                << " backward timestamp step(s) in this file";
      if (data.rows_dropped_session > 0) {
        std::cout << " -> --session-longest dropped " << data.rows_dropped_session
                  << " rows";
      } else {
        std::cout << "  *** WARNING: dt < 0 corrupts the estimator."
                     " Re-run with --session-longest ***";
      }
      std::cout << "\n";
    }
    std::cout << "gnss fixes   : " << data.gnss.size()
              << (use_gnss ? "" : "  (--no-gnss)") << "\n";
    std::cout << "vehicle      : " << veh << (two_wheeler ? " (lean-aware)" : " (car-style)")
              << "\n";
    std::cout << "graph        : " << graph_name << "\n";
    std::cout << "load time    : " << std::setprecision(3) << load_s << " s\n";
    if (!input.empty()) {
      std::cout << "bound columns:\n";
      for (const auto& kv : data.bound) {
        std::cout << "  " << std::setw(13) << std::left << kv.first << " <- \""
                  << kv.second << "\"\n";
      }
      std::cout << std::right;
    }
  }

  // The core designs its Butterworth at 8 Hz. Below ~20 Hz that is above
  // Nyquist, so clamp and say so rather than shipping an unstable filter.
  double fc = 8.0;
  if (hz < 20.0) {
    fc = 0.4 * hz;
    if (!quiet) {
      std::cout << "note         : lowpass cutoff clamped 8.0 -> " << std::setprecision(2)
                << fc << " Hz (input is " << hz << " Hz)\n";
    }
  }

  std::vector<nav::INavState> traj;
  std::vector<double> lat_us;
  double engine_s = 0.0;
  std::size_t stepped = 0;
  std::size_t denied = 0;

  if (mode == "batch") {
    nav::ILogMeta meta;
    meta.phone_model = mapping.phone_model;
    meta.mount_type = mapping.mount_type;
    meta.vehicle = veh;
    meta.leans = two_wheeler;
    meta.imu_hz = hz;
    meta.route_id = mapping.name;
    meta.loop_closure = origin;

    nav::RunOpts opts;
    opts.two_wheeler = two_wheeler;
    opts.target_hz = hz;
    opts.has_graph = false;

    const auto t0 = std::chrono::steady_clock::now();
    nav::EngineResult r;
    for (int k = 0; k < repeat; ++k) {
      r = nav::runEngine(data.imu, data.gnss, meta, opts);
    }
    const auto t1 = std::chrono::steady_clock::now();
    engine_s = std::chrono::duration<double>(t1 - t0).count();
    traj = r.ours;
    // Batch mode runs BOTH the lean-aware path and the car-style baseline,
    // so per-sample cost is charged over 2 x samples x repeat.
    stepped = traj.size() * 2 * static_cast<std::size_t>(repeat);
  } else if (mode == "stream") {
    StreamCfg cfg;
    cfg.hz = hz;
    cfg.filter_fc = fc;
    cfg.two_wheeler = two_wheeler;
    cfg.use_graph = graph_name == "campus";
    cfg.particles = particles;
    cfg.origin = origin;
    const nav::IRoadGraph graph =
        cfg.use_graph ? nav::defaultCampusGraph() : nav::IRoadGraph{};

    if (bench) lat_us.reserve(data.imu.size() * static_cast<std::size_t>(repeat));
    for (int k = 0; k < repeat; ++k) {
      EdgeStream eng(cfg, data.gnss, graph);
      std::vector<nav::INavState> pass;
      pass.reserve(data.imu.size());
      const auto t0 = std::chrono::steady_clock::now();
      for (const nav::ISensorFrame& f : data.imu) {
        if (bench) {
          const auto s0 = std::chrono::steady_clock::now();
          const nav::INavState st = eng.step(f);
          const auto s1 = std::chrono::steady_clock::now();
          lat_us.push_back(std::chrono::duration<double, std::micro>(s1 - s0).count());
          pass.push_back(st);
        } else {
          pass.push_back(eng.step(f));
        }
      }
      const auto t1 = std::chrono::steady_clock::now();
      engine_s += std::chrono::duration<double>(t1 - t0).count();
      stepped += data.imu.size();
      denied = eng.denied();
      if (k == repeat - 1) traj = std::move(pass);
    }
  } else {
    std::cerr << "idr_edge: --mode must be stream or batch\n";
    return 2;
  }

  bool finite = true;
  for (const nav::INavState& s : traj) {
    if (!std::isfinite(s.lat) || !std::isfinite(s.lon)) finite = false;
  }

  if (!out_path.empty()) {
    std::ofstream o(out_path, std::ios::binary);
    if (!o) {
      std::cerr << "idr_edge: cannot write " << out_path << "\n";
      return 1;
    }
    o << "t_ns,lat,lon,alt,ve,vn,vu,roll_deg,pitch_deg,yaw_deg,lean_deg,speed,mode,"
         "edge_id,gnss_aided\n";
    o << std::fixed;
    for (const nav::INavState& s : traj) {
      o << s.t_ns << ','
        << std::setprecision(9) << s.lat << ',' << s.lon << ','
        << std::setprecision(3) << s.alt << ','
        << s.ve << ',' << s.vn << ',' << s.vu << ','
        << nav::rad2deg(s.roll) << ',' << nav::rad2deg(s.pitch) << ','
        << nav::rad2deg(s.yaw) << ',' << nav::rad2deg(s.lean) << ','
        << s.speed << ','
        << s.mode << ',' << s.edge_id << ',' << (s.gnss_aided ? 1 : 0) << '\n';
    }
    if (!quiet) std::cout << "wrote        : " << out_path << " (" << traj.size() << " rows)\n";
  }

  if (!quiet || bench) {
    const std::vector<nav::Lla> lla = nav::statesToLla(traj);
    const double dist = nav::pathLength(lla);
    std::cout << "--- trajectory ---\n";
    std::cout << "states       : " << traj.size() << (finite ? "  (all finite)" : "  (NON-FINITE)")
              << "\n";
    std::cout << "path length  : " << std::fixed << std::setprecision(1) << dist << " m\n";
    if (!lla.empty()) {
      std::cout << "start        : " << std::setprecision(6) << lla.front().lat << ", "
                << lla.front().lon << "\n";
      std::cout << "end          : " << lla.back().lat << ", " << lla.back().lon << "\n";
      std::cout << "closure err  : " << std::setprecision(1)
                << nav::loopClosureError(lla, origin) << " m vs origin\n";
    }
    if (mode == "stream") {
      std::cout << "gnss-denied  : " << denied << " / " << traj.size() << " samples\n";
    }
  }

  if (bench) {
    const double per_sample_us = stepped > 0 ? (engine_s * 1e6) / static_cast<double>(stepped) : 0;
    const double thr = engine_s > 0 ? static_cast<double>(stepped) / engine_s : 0;
    std::cout << "--- benchmark (" << mode << ") ---\n";
    std::cout << std::fixed;
    std::cout << "samples proc : " << stepped;
    if (mode == "batch") std::cout << "  (ours + car-style baseline)";
    std::cout << "\n";
    std::cout << "engine time  : " << std::setprecision(4) << engine_s << " s\n";
    std::cout << "throughput   : " << std::setprecision(0) << thr << " Hz\n";
    std::cout << "mean latency : " << std::setprecision(2) << per_sample_us << " us/sample\n";
    if (!lat_us.empty()) {
      std::vector<double> v = lat_us;
      const double p50 = percentile(v, 0.50);
      const double p99 = percentile(v, 0.99);
      const double mx = v.back();
      std::cout << "p50 latency  : " << std::setprecision(2) << p50 << " us\n";
      std::cout << "p99 latency  : " << std::setprecision(2) << p99 << " us\n";
      std::cout << "max latency  : " << std::setprecision(2) << mx << " us\n";
    }
    const double rss = peakRssMb();
    if (rss >= 0) std::cout << "peak memory  : " << std::setprecision(1) << rss << " MB\n";
    std::cout << "realtime x   : " << std::setprecision(1) << (hz > 0 ? thr / hz : 0)
              << "  (throughput / " << std::setprecision(0) << hz << " Hz input rate)\n";
    std::cout << "200 Hz req   : " << (thr >= 200.0 ? "MET" : "NOT MET") << "\n";
  }

  return finite ? 0 : 1;
}
