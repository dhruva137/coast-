#include "nav/math.h"

#include <cmath>
#include <cstddef>

namespace nav {

double clamp(double x, double a, double b) {
  if (x < a) return a;
  if (x > b) return b;
  return x;
}

double hypot3(double x, double y, double z) {
  return std::sqrt(x * x + y * y + z * z);
}

double wrapPi(double a) {
  double x = std::fmod(a + kPi, 2.0 * kPi);
  if (x < 0.0) x += 2.0 * kPi;
  return x - kPi;
}

double wrap360(double deg) {
  double x = std::fmod(deg, 360.0);
  if (x < 0.0) x += 360.0;
  return x;
}

double deg2rad(double d) { return d * kDeg; }
double rad2deg(double r) { return r * kRad; }

Mat3 mat3Ident() { return Mat3{{1, 0, 0, 0, 1, 0, 0, 0, 1}}; }

Mat3 mat3Mul(const Mat3& a, const Mat3& b) {
  Mat3 r{};
  for (int i = 0; i < 3; ++i) {
    for (int j = 0; j < 3; ++j) {
      r[static_cast<std::size_t>(i * 3 + j)] =
          a[static_cast<std::size_t>(i * 3 + 0)] * b[static_cast<std::size_t>(0 * 3 + j)] +
          a[static_cast<std::size_t>(i * 3 + 1)] * b[static_cast<std::size_t>(1 * 3 + j)] +
          a[static_cast<std::size_t>(i * 3 + 2)] * b[static_cast<std::size_t>(2 * 3 + j)];
    }
  }
  return r;
}

Mat3 mat3T(const Mat3& a) {
  return Mat3{{a[0], a[3], a[6], a[1], a[4], a[7], a[2], a[5], a[8]}};
}

Vec3 mat3Vec(const Mat3& a, const Vec3& v) {
  return Vec3{{a[0] * v[0] + a[1] * v[1] + a[2] * v[2],
               a[3] * v[0] + a[4] * v[1] + a[5] * v[2],
               a[6] * v[0] + a[7] * v[1] + a[8] * v[2]}};
}

Mat3 skew(double x, double y, double z) {
  return Mat3{{0, -z, y, z, 0, -x, -y, x, 0}};
}

Mat3 so3Exp(double wx, double wy, double wz) {
  const double th = hypot3(wx, wy, wz);
  if (th < 1e-12) {
    const Mat3 K = skew(wx, wy, wz);
    Mat3 out = mat3Ident();
    for (int i = 0; i < 9; ++i) out[static_cast<std::size_t>(i)] += K[static_cast<std::size_t>(i)];
    return out;
  }
  const double kx = wx / th, ky = wy / th, kz = wz / th;
  const Mat3 K = skew(kx, ky, kz);
  const Mat3 K2 = mat3Mul(K, K);
  const double s = std::sin(th);
  const double c = 1.0 - std::cos(th);
  Mat3 out = mat3Ident();
  for (int i = 0; i < 9; ++i) {
    const auto u = static_cast<std::size_t>(i);
    out[u] += s * K[u] + c * K2[u];
  }
  return out;
}

Mat3 rpyToMat(double roll, double pitch, double yaw) {
  const double cr = std::cos(roll), sr = std::sin(roll);
  const double cp = std::cos(pitch), sp = std::sin(pitch);
  const double cy = std::cos(yaw), sy = std::sin(yaw);
  return Mat3{{
      cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr,
      sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr,
      -sp,     cp * sr,                cp * cr,
  }};
}

void matToRpy(const Mat3& R, double& roll, double& pitch, double& yaw) {
  pitch = std::asin(clamp(-R[6], -1.0, 1.0));
  roll = std::atan2(R[7], R[8]);
  yaw = std::atan2(R[3], R[0]);
}

void metersPerDeg(double lat_deg, double& m_lat, double& m_lon) {
  const double lat = deg2rad(lat_deg);
  m_lat = 111132.92 - 559.82 * std::cos(2.0 * lat) + 1.175 * std::cos(4.0 * lat);
  m_lon = 111412.84 * std::cos(lat) - 93.5 * std::cos(3.0 * lat);
}

Lla enuToLla(const Lla& origin, double e, double n, double u) {
  double m_lat = 1, m_lon = 1;
  metersPerDeg(origin.lat, m_lat, m_lon);
  Lla out;
  out.lat = origin.lat + n / m_lat;
  out.lon = origin.lon + e / m_lon;
  out.alt = origin.alt + u;
  return out;
}

Enu llaToEnu(const Lla& origin, double lat, double lon, double alt) {
  double m_lat = 1, m_lon = 1;
  metersPerDeg(origin.lat, m_lat, m_lon);
  Enu out;
  out.e = (lon - origin.lon) * m_lon;
  out.n = (lat - origin.lat) * m_lat;
  out.u = alt - origin.alt;
  return out;
}

double haversineM(double lat1, double lon1, double lat2, double lon2) {
  const double R = 6371000.0;
  const double p1 = deg2rad(lat1);
  const double p2 = deg2rad(lat2);
  const double dp = deg2rad(lat2 - lat1);
  const double dl = deg2rad(lon2 - lon1);
  const double a = std::sin(dp / 2.0) * std::sin(dp / 2.0) +
                   std::cos(p1) * std::cos(p2) * std::sin(dl / 2.0) * std::sin(dl / 2.0);
  return 2.0 * R * std::asin(clamp(std::sqrt(a), 0.0, 1.0));
}

double headingBetween(double lat1, double lon1, double lat2, double lon2) {
  const double p1 = deg2rad(lat1);
  const double p2 = deg2rad(lat2);
  const double dl = deg2rad(lon2 - lon1);
  const double y = std::sin(dl) * std::cos(p2);
  const double x = std::cos(p1) * std::sin(p2) - std::sin(p1) * std::cos(p2) * std::cos(dl);
  return wrap360(rad2deg(std::atan2(y, x)));
}

Rng32::Rng32(std::uint32_t seed) : state(seed) {}

double Rng32::next() {
  std::uint32_t a = state;
  a += 0x6d2b79f5u;
  std::uint32_t t = (a ^ (a >> 15)) * (1u | a);
  t = (t + ((t ^ (t >> 7)) * (61u | t))) ^ t;
  state = a;
  return static_cast<double>(t ^ (t >> 14)) / 4294967296.0;
}

double gauss(Rng32& rng) {
  const double u = clamp(rng.next(), 1e-12, 1.0);
  const double v = rng.next();
  return std::sqrt(-2.0 * std::log(u)) * std::cos(2.0 * kPi * v);
}

} // namespace nav
