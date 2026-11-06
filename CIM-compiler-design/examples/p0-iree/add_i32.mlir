func.func @add_i32(%lhs: tensor<4xi32>, %rhs: tensor<4xi32>) -> tensor<4xi32> {
  %0 = arith.addi %lhs, %rhs : tensor<4xi32>
  return %0 : tensor<4xi32>
}
