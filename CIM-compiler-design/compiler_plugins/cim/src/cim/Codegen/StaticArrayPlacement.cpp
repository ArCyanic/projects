#include "cim/Codegen/StaticArrayPlacement.h"

#include <algorithm>
#include <system_error>
#include <utility>

#include "llvm/ADT/STLExtras.h"

namespace mlir::iree_compiler::IREE::CIM {
namespace {

static bool overlaps(const StaticArrayRegion &a, const StaticArrayRegion &b) {
  return a.row < b.row + b.rows && b.row < a.row + a.rows &&
         a.column < b.column + b.columns && b.column < a.column + a.columns;
}

} // namespace

DenseWeight
DenseWeight::blockDiagonal(llvm::ArrayRef<const DenseWeight *> weights) {
  int64_t k = 0, n = 0;
  for (const DenseWeight *weight : weights) {
    k += weight->k;
    n += weight->n;
  }
  DenseWeight result{k, n, llvm::SmallVector<int8_t>(k * n, 0)};
  int64_t kOffset = 0, nOffset = 0;
  for (const DenseWeight *weight : weights) {
    for (int64_t row = 0; row < weight->k; ++row)
      llvm::copy(llvm::ArrayRef(weight->data).slice(row * weight->n, weight->n),
                 result.data.begin() + (kOffset + row) * n + nOffset);
    kOffset += weight->k;
    nOffset += weight->n;
  }
  return result;
}

llvm::Expected<StaticArrayPlan>
planStaticArray(llvm::ArrayRef<const DenseWeight *> weights, int64_t arrayRows,
                int64_t arrayColumns) {
  StaticArrayPlan plan;
  for (const DenseWeight *entry : weights) {
    const DenseWeight &weight = *entry;
    if (weight.k > arrayRows)
      return llvm::createStringError(std::errc::invalid_argument,
                                     "weight rows exceed CIM Array capacity");
    auto &slices = plan.uses.emplace_back();
    for (int64_t n = 0; n < weight.n; n += arrayColumns) {
      int64_t width = std::min(arrayColumns, weight.n - n);
      llvm::SmallVector<int8_t> data;
      data.reserve(weight.k * width);
      for (int64_t k = 0; k < weight.k; ++k)
        llvm::append_range(
            data, llvm::ArrayRef(weight.data)
                      .slice(k * weight.n + n, static_cast<size_t>(width)));
      auto found = llvm::find_if(plan.regions, [&](const auto &region) {
        return region.rows == weight.k && region.columns == width &&
               region.data == data;
      });
      unsigned index = found - plan.regions.begin();
      if (found == plan.regions.end()) {
        index = plan.regions.size();
        plan.regions.push_back({0, 0, weight.k, width, std::move(data)});
      }
      slices.push_back({index, n});
    }
  }

  llvm::SmallVector<unsigned> order(plan.regions.size());
  for (unsigned i = 0; i < order.size(); ++i)
    order[i] = i;
  llvm::stable_sort(order, [&](unsigned a, unsigned b) {
    const auto &x = plan.regions[a];
    const auto &y = plan.regions[b];
    if (x.rows * x.columns != y.rows * y.columns)
      return x.rows * x.columns > y.rows * y.columns;
    if (x.rows != y.rows)
      return x.rows > y.rows;
    if (x.columns != y.columns)
      return x.columns > y.columns;
    return std::lexicographical_compare(y.data.begin(), y.data.end(),
                                        x.data.begin(), x.data.end());
  });

  llvm::SmallVector<unsigned> placed;
  for (unsigned index : order) {
    auto &region = plan.regions[index];
    bool found = false;
    llvm::SmallVector<int64_t> rows{0};
    for (unsigned other : placed)
      rows.push_back(plan.regions[other].row + plan.regions[other].rows);
    llvm::sort(rows);
    rows.erase(llvm::unique(rows), rows.end());
    llvm::sort(placed, [&](unsigned a, unsigned b) {
      return plan.regions[a].column < plan.regions[b].column;
    });
    for (int64_t row : rows) {
      region.row = row;
      region.column = 0;
      // Slide right over blockers in column order to find this row's first gap.
      for (unsigned other : placed) {
        const auto &blocker = plan.regions[other];
        if (overlaps(region, blocker))
          region.column = blocker.column + blocker.columns;
      }
      found = row + region.rows <= arrayRows &&
              region.column + region.columns <= arrayColumns;
      if (found)
        break;
    }
    if (!found)
      return llvm::createStringError(std::errc::invalid_argument,
                                     "no static CIM Array layout found");
    placed.push_back(index);
  }
  return plan;
}

} // namespace mlir::iree_compiler::IREE::CIM
