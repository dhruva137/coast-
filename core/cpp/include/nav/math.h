#pragma once

// SO(3) exponential, ZYX roll-pitch-yaw, ENU ↔ LLA, angle wrap.
// No external linear-algebra dependency.

#include "nav/types.h"

namespace nav {

double clamp(double x, double a, double b);
double hypot3(double x, double y, double z);
double wrapPi(double a);
double wrap360(double deg);
double deg2rad(double d);
double rad2deg(double r);

Mat3 mat3Ident();
Mat3 mat3Mul(const Mat3& a, const Mat3& b);
Mat3 mat3T(const Mat3& a);
Vec3 mat3Vec(const Mat3& a, const Vec3& v);
Mat3 skew(double x, double y, double z);

/** Rodrigues: Exp([wx, wy, wz]^) on SO(3). Argument is a rotation vector (rad). */
Mat3 so3Exp(double wx, double wy, double wz);

/** Body-to-nav ZYX: R = Rz(yaw) Ry(pitch) Rx(roll). */
Mat3 rpyToMat(double roll, double pitch, double yaw);
void matToRpy(const Mat3& R, double& roll, double& pitch, double& yaw);

/** WGS-84 metres-per-degree at geodetic latitude (deg). */
void metersPerDeg(double lat_deg, double& m_lat, double& m_lon);

Lla enuToLla(const Lla& origin, double e, double n, double u);
Enu llaToEnu(const Lla& origin, double lat, double lon, double alt);

double haversineM(double lat1, double lon1, double lat2, double lon2);
double headingBetween(double lat1, double lon1, double lat2, double lon2);

/** Deterministic PRNG (mulberry32). Returns U[0, 1). */
struct Rng32 {
  std::uint32_t state;
  explicit Rng32(std::uint32_t seed = 26168u);
  double next();
};

double gauss(Rng32& rng);

} // namespace nav
