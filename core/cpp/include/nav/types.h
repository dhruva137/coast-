#pragma once

// Frozen sensor / estimator API. Field names match SIH26168_PROJECT_BIBLE.md §5.8.
// SI units throughout. Timestamps are monotonic nanoseconds (t_ns).

#include <array>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace nav {

constexpr double kG = 9.80665;
constexpr double kPi = 3.14159265358979323846264338327950288;
constexpr double kDeg = kPi / 180.0;
constexpr double kRad = 180.0 / kPi;

using Mat3 = std::array<double, 9>; // row-major
using Vec3 = std::array<double, 3>;

struct Lla {
  double lat = 0; // deg
  double lon = 0; // deg
  double alt = 0; // m
};

struct Enu {
  double e = 0;
  double n = 0;
  double u = 0;
};

/** Uniform IMU + aiding frame at one timestamp. SI units. */
struct ISensorFrame {
  std::int64_t t_ns = 0;
  double ax = 0, ay = 0, az = 0; // m/s^2, specific force
  double gx = 0, gy = 0, gz = 0; // rad/s
  double mx = 0, my = 0, mz = 0; // uT (unused by core)
  double pressure_hpa = 1013.25;
  double lux = 0;
};

struct IGnssFix {
  std::int64_t t_ns = 0;
  double lat = 0, lon = 0, alt = 0;
  double speed = 0;   // m/s
  double bearing = 0; // deg, clockwise from north
  double acc_h = 5;
  double acc_v = 8;
  int n_sats = 0;
};

struct ILogMeta {
  std::string phone_model;
  std::string mount_type; // handlebar | pocket | tankbag | frame | dash
  std::string vehicle;    // car | scooter | motorcycle | bicycle
  std::string rider;
  std::string route_id;
  Lla loop_closure;
  std::string notes;
  double imu_hz = 50;
  bool leans = true;
};

struct INavState {
  std::int64_t t_ns = 0;
  double lat = 0, lon = 0, alt = 0;
  double ve = 0, vn = 0, vu = 0;
  double roll = 0, pitch = 0, yaw = 0; // rad
  double lean = 0;                     // φ, rad
  double speed = 0;
  Mat3 P_pos{{1, 0, 0, 0, 1, 0, 0, 0, 1}};
  bool gnss_aided = false;
  std::string edge_id;
  std::map<std::string, double> branch_posteriors;
  std::string mode = "ins"; // gnss | ins | graph | coast
};

struct IMetrics {
  double loop_closure_m = 0;
  double distance_m = 0;
  double drift_pct = 0;
  double ate_m = 0;
  double rte_m = 0;
  double branch_accuracy = 0;
  double lean_rmse_deg = 0;
  double latency_ms = 0;
};

struct IGraphNode {
  std::string id;
  double lat = 0, lon = 0, alt = 0;
  std::string kind; // outdoor | tunnel | garage | junction | ramp | portal
};

struct IGraphEdge {
  std::string id;
  std::string from;
  std::string to;
  double heading_deg = 0;
  double length_m = 1;
  bool tunnel = false;
  bool garage = false;
  double light_spacing_m = 0; // 0 = none; COUNT pulses, do not phase-match
  double grade = 0;
  int lanes = 1;
};

struct IRoadGraph {
  std::string name;
  Lla origin;
  std::vector<IGraphNode> nodes;
  std::vector<IGraphEdge> edges;
};

struct IParticle {
  std::string edge_id;
  double s = 0; // arc-length fraction along edge, [0, 1)
  double weight = 1;
  double heading = 0; // deg
};

} // namespace nav
