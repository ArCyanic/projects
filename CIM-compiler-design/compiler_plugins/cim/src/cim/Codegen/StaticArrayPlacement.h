#ifndef CIM_COMPILER_PLUGIN_CIM_CODEGEN_STATICARRAYPLACEMENT_H_
#define CIM_COMPILER_PLUGIN_CIM_CODEGEN_STATICARRAYPLACEMENT_H_

#include <cstdint>

#include "llvm/ADT/ArrayRef.h"
#include "llvm/ADT/SmallVector.h"
#include "llvm/Support/Error.h"

namespace mlir::iree_compiler::IREE::CIM {

/// A row-major i8 matrix shared by tensor fusion and linked MVM planning.
struct DenseWeight {
  int64_t k;
  int64_t n;
  llvm::SmallVector<int8_t> data;

  /// Places the matrices on the diagonal and fills all other cells with zero.
  /// Repeated pointers express weight replication without copying the inputs.
  static DenseWeight blockDiagonal(llvm::ArrayRef<const DenseWeight *> weights);
};

struct StaticArrayRegion {
  int64_t row;
  int64_t column;
  int64_t rows;
  int64_t columns;
  llvm::SmallVector<int8_t> data;
};

struct StaticArraySlice {
  unsigned region;
  int64_t nOffset;
};

struct StaticArrayPlan {
  llvm::SmallVector<StaticArrayRegion> regions;
  llvm::SmallVector<llvm::SmallVector<StaticArraySlice>> uses;
};

llvm::Expected<StaticArrayPlan>
planStaticArray(llvm::ArrayRef<const DenseWeight *> weights, int64_t arrayRows,
                int64_t arrayColumns);

} // namespace mlir::iree_compiler::IREE::CIM

#endif // CIM_COMPILER_PLUGIN_CIM_CODEGEN_STATICARRAYPLACEMENT_H_
