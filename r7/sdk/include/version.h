// R7 locally generated version macros from exact-revision CMake/version.h.in.
// Upstream src/CMakeLists.txt specifies major=2, minor=17, default patch=0.
#ifndef _XRT_VERSION_H_
#define _XRT_VERSION_H_
#define XRT_VERSION(major, minor) ((major << 16) + (minor))
#define XRT_VERSION_CODE XRT_VERSION(2, 17)
#define XRT_MAJOR(code) ((code >> 16))
#define XRT_MINOR(code) (code - ((code >> 16) << 16))
#define XRT_PATCH 0
#endif
