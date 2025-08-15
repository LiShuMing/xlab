// #define WIN32_LEAN_AND_MEAN
// #include "windows.h"
#include <cstdio>
#include <cstdlib>

#define ALWAYS_INLINE __attribute__((__always_inline__,__nodebug__))
//#define ALWAYS_INLINE 
#define VEC_SCALAR 1
#define VEC_OP 0
#define VEC_OP_MEMBER 0
#define VEC_SSE_RAW 0
#define VEC_SSE 0
#define VEC_SSE_OP 0
#define VEC_SSE_OP_VEC 0
#define VEC_SSE_OP_MEM_VEC 0
#define VEC_BUILTIN_OCL 0
#define VEC_BUILTIN_GCC 0
#define VEC_BUILTIN_OCL_WRAP 0

#if VEC_SCALAR

struct float3 {
	float x, y, z, pad;
};

#elif VEC_OP

struct float3 {
	float x, y, z, pad;
};

ALWAYS_INLINE float3& operator+=(float3& a, const float3& b) {
	a.x += b.x;
	a.y += b.y;
	a.z += b.z;
	return a;
}

ALWAYS_INLINE float3 operator-(const float3& a, const float3& b) {
	return float3{ a.x - b.x, a.y - b.y, a.z - b.z };
}

ALWAYS_INLINE float3 operator/(const float3& a, float b) {
	return float3{ a.x / b, a.y / b, a.z / b };
}

ALWAYS_INLINE float3 operator*(float a, const float3& b) {
	return float3{ a * b.x, a * b.y, a * b.z };
}

#elif VEC_OP_MEMBER

struct float3 {
	float x, y, z, pad;

	ALWAYS_INLINE float3& operator+=( const float3& b) {
		x += b.x;
		y += b.y;
		z += b.z;
		return *this;
	}

	ALWAYS_INLINE float3 operator-(const float3& b) const {
		return float3{ x - b.x, y - b.y, z - b.z };
	}

	ALWAYS_INLINE float3 operator/(float b) const {
		return float3{ x / b, y / b, z / b };
	}
};

ALWAYS_INLINE float3 operator*(float a, const float3& b) {
	return float3{ a * b.x, a * b.y, a * b.z };
}

#elif VEC_SSE_RAW

#include "immintrin.h"

typedef __m128 float3;

#elif VEC_SSE

#include "immintrin.h"

struct float3 {
	union {
		__m128 vec;
		struct { float x, y, z, pad; };
	};
};

#elif VEC_SSE_OP

#include "immintrin.h"

struct float3 {
	union {
		__m128 vec;
		struct { float x, y, z, pad; };
	};
};


ALWAYS_INLINE float3& operator+=(float3& a, const float3& b) {
	a.vec = _mm_add_ps(a.vec, b.vec);
	return a;
}

ALWAYS_INLINE float3 operator-(const float3& a, const float3& b) {
	return float3{ _mm_sub_ps(a.vec, b.vec) };
}

ALWAYS_INLINE float3 operator/(const float3& a, float b) {
	return float3{ _mm_div_ps(a.vec, _mm_set1_ps(b)) };
}

ALWAYS_INLINE float3 operator*(float a, const float3& b) {
	return float3{ _mm_mul_ps(_mm_set1_ps(a), b.vec) };
}

#elif VEC_SSE_OP_VEC

#include "immintrin.h"

struct float3 {
	union {
		__m128 vec;
		struct { float x, y, z, pad; };
	};
};

__vectorcall ALWAYS_INLINE float3& operator+=(float3& a, const float3& b) {
	a.vec = _mm_add_ps(a.vec, b.vec);
	return a;
}

__vectorcall ALWAYS_INLINE float3 operator-(const float3& a, const float3& b) {
	return float3{ _mm_sub_ps(a.vec, b.vec) };
}

__vectorcall ALWAYS_INLINE float3 operator/(const float3& a, float b) {
	return float3{ _mm_div_ps(a.vec, _mm_set1_ps(b)) };
}

__vectorcall ALWAYS_INLINE float3 operator*(float a, const float3& b) {
	return float3{ _mm_mul_ps(_mm_set1_ps(a), b.vec) };
}

#elif VEC_SSE_OP_MEM_VEC

#include "immintrin.h"

struct float3 {
	union {
		__m128 vec;
		struct { float x, y, z, pad; };
	};

	__vectorcall ALWAYS_INLINE float3& operator+=(const float3& b) {
		vec = _mm_add_ps(vec, b.vec);
		return *this;
	}

	__vectorcall ALWAYS_INLINE float3 operator-(const float3& b) const {
		return float3{ _mm_sub_ps(vec, b.vec) };
	}

	__vectorcall ALWAYS_INLINE float3 operator/(float b) const {
		return float3{ _mm_div_ps(vec, _mm_set1_ps(b)) };
	}
};

__vectorcall ALWAYS_INLINE float3 operator*(float a, const float3& b) {
	return float3{ _mm_mul_ps(_mm_set1_ps(a), b.vec) };
}

#elif VEC_BUILTIN_OCL

typedef float float3 __attribute__((ext_vector_type(3), __aligned__(16)));
static_assert(sizeof(float3) == 4 * sizeof(float), "Unexpected vector size");

#elif VEC_BUILTIN_GCC

typedef float float3 __attribute__((__vector_size__(16), __aligned__(16)));
static_assert(sizeof(float3) == 4 * sizeof(float), "Unexpected vector size");

#elif VEC_BUILTIN_OCL_WRAP

typedef float v4f __attribute__((ext_vector_type(4)));

struct float3 {
	union {
		v4f vec;
		struct { float x, y, z, pad; };
	};
};

ALWAYS_INLINE float3& operator+=(float3& a, const float3& b) {
	a.vec += b.vec;
	return a;
}

ALWAYS_INLINE float3 operator-(const float3& a, const float3& b) {
	return float3{ a.vec - b.vec };
}

ALWAYS_INLINE float3 operator/(const float3& a, float b) {
	return float3{ a.vec / b };
}

ALWAYS_INLINE float3 operator*(float a, const float3& b) {
	return float3{ a * b.vec };
}

#endif

int main()
{
	constexpr static int kNumParticles = 1024 * 64;
	constexpr static int kNumCenters = 10;

	float3* centerPos = (float3*)malloc(sizeof(float3) * kNumCenters);
	memset(centerPos, 0, sizeof(float3) * kNumCenters);
	float* centerMass = (float*)malloc(sizeof(float) * kNumCenters);
	memset(centerMass, 0, sizeof(float) * kNumCenters);
	float3* particlePos = (float3*)malloc(sizeof(float3) * kNumParticles);
	memset(particlePos, 0, sizeof(float3) * kNumParticles);
	float3* particleVel = (float3*)malloc(sizeof(float3) * kNumParticles);
	memset(particleVel, 0, sizeof(float3) * kNumParticles);

	constexpr static int kNumIterations = 500;

	getchar();

	double mean = 0.0, m2 = 0.0;
	double min = 1;
	double max = 0;
	LARGE_INTEGER freq, start, end;
	QueryPerformanceFrequency(&freq);
	
	for (int iter = 0; iter < kNumIterations; iter++) {
		QueryPerformanceCounter(&start);

		for (int p = 0; p < kNumParticles; p++) {
			float3 vel = particleVel[p];
			float3 pos = particlePos[p];
			for (int c = 0; c < kNumCenters; c++) {
				float3 cPos = centerPos[c];

#if VEC_SCALAR
				float dx = cPos.x - pos.x;
				float dy = cPos.y - pos.y;
				float dz = cPos.z - pos.z;

				float squared = dx * dx + dy * dy + dz * dz;
				float f = centerMass[c] / squared;

				float distance = sqrtf(squared);
				if (distance < 10)
					distance = 10;

				dx *= f * dx / distance;
				dy *= f * dy / distance;
				dz *= f * dz / distance;

				// This is assuming a time step of 1/60
				vel.x += dx / 60;
				vel.y += dy / 60;
				vel.z += dz / 60;
#elif VEC_SSE_RAW
				float3 delta = _mm_sub_ps(cPos, pos);

				float dx = _mm_cvtss_f32(delta);
				float dy = _mm_cvtss_f32(_mm_shuffle_ps(delta, delta, _MM_SHUFFLE(1, 1, 1, 1)));
				float dz = _mm_cvtss_f32(_mm_shuffle_ps(delta, delta, _MM_SHUFFLE(2, 2, 2, 2)));
				float squared = dx * dx + dy * dy + dz * dz;
				float f = centerMass[c] / squared;

				float distance = sqrtf(squared);
				if (distance < 10)
					distance = 10;

				delta = _mm_div_ps(_mm_mul_ps(_mm_set1_ps(f), delta), _mm_set1_ps(distance));
				vel = _mm_add_ps(vel, _mm_div_ps(delta, _mm_set1_ps(60)));
#elif VEC_SSE
				float3 delta{ _mm_sub_ps(cPos.vec, pos.vec) };

				float dx = _mm_cvtss_f32(delta.vec);
				float dy = _mm_cvtss_f32(_mm_shuffle_ps(delta.vec, delta.vec, _MM_SHUFFLE(1, 1, 1, 1)));
				float dz = _mm_cvtss_f32(_mm_shuffle_ps(delta.vec, delta.vec, _MM_SHUFFLE(2, 2, 2, 2)));
				float squared = dx * dx + dy * dy + dz * dz;
				float f = centerMass[c] / squared;

				float distance = sqrtf(squared);
				if (distance < 10)
					distance = 10;

				delta.vec = _mm_div_ps(_mm_mul_ps(_mm_set1_ps(f), delta.vec), _mm_set1_ps(distance));
				vel.vec = _mm_add_ps(vel.vec, _mm_div_ps(delta.vec, _mm_set1_ps(60)));
#else
				float3 delta = cPos - pos;

#if VEC_BUILTIN_GCC
				float dx = delta[0];
				float dy = delta[1];
				float dz = delta[2];
#else
				float dx = delta.x;
				float dy = delta.y;
				float dz = delta.z;
#endif
				float squared = dx * dx + dy * dy + dz * dz;
				float f = centerMass[c] / squared;

				float distance = sqrtf(squared);
				if (distance < 10)
					distance = 10;

				delta = f * delta / distance;
				vel += delta / 60;
#endif
			}
			particleVel[p] = vel;
		}

		QueryPerformanceCounter(&end);

		// in microseconds
		double elapsed = (double)(end.QuadPart - start.QuadPart) / freq.QuadPart * 1000 * 1000;
		double delta = elapsed - mean;
		mean += delta / (iter + 1);
		m2 += delta * (elapsed - mean);

		if (elapsed > max)
			max = elapsed;
		if (elapsed < min)
			min = elapsed;
	}
	double variance = m2 / kNumIterations;
	double stddev = sqrt(variance);

	printf("Mean: %fmus\n", mean);
	printf("Stddev: %fmus\n", stddev);
	printf("Min: %fmus\n", min);
	printf("Max: %fmus\n", max);
	return 0;
}