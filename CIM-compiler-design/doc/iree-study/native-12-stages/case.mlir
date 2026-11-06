// Two-layer residual MLP plus a row reduction. All operands are runtime inputs.
// H = relu(X @ W1 + b1), Y = H @ W2 + b2 + R, S[i] = sum_j Y[i,j].
module @residual_mlp {
  func.func @main(
      %x: tensor<16x32xf32>, %w1: tensor<32x64xf32>,
      %b1: tensor<64xf32>, %w2: tensor<64x32xf32>,
      %b2: tensor<32xf32>, %r: tensor<16x32xf32>)
      -> (tensor<16x32xf32>, tensor<16xf32>) {
    %zero = stablehlo.constant dense<0.0> : tensor<f32>
    %m1 = stablehlo.dot_general %x, %w1,
      contracting_dims = [1] x [0], precision = [DEFAULT, DEFAULT]
      : (tensor<16x32xf32>, tensor<32x64xf32>) -> tensor<16x64xf32>
    %bias1 = stablehlo.broadcast_in_dim %b1, dims = [1]
      : (tensor<64xf32>) -> tensor<16x64xf32>
    %a1 = stablehlo.add %m1, %bias1 : tensor<16x64xf32>
    %zeros = stablehlo.broadcast_in_dim %zero, dims = []
      : (tensor<f32>) -> tensor<16x64xf32>
    %h = stablehlo.maximum %a1, %zeros : tensor<16x64xf32>
    %m2 = stablehlo.dot_general %h, %w2,
      contracting_dims = [1] x [0], precision = [DEFAULT, DEFAULT]
      : (tensor<16x64xf32>, tensor<64x32xf32>) -> tensor<16x32xf32>
    %bias2 = stablehlo.broadcast_in_dim %b2, dims = [1]
      : (tensor<32xf32>) -> tensor<16x32xf32>
    %a2 = stablehlo.add %m2, %bias2 : tensor<16x32xf32>
    %y = stablehlo.add %a2, %r : tensor<16x32xf32>
    %s = stablehlo.reduce(%y init: %zero) applies stablehlo.add across dimensions = [1]
      : (tensor<16x32xf32>, tensor<f32>) -> tensor<16xf32>
    return %y, %s : tensor<16x32xf32>, tensor<16xf32>
  }
}
