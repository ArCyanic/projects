module @residual_mlp {
  func.func @main(%arg0: tensor<16x32xf32>, %arg1: tensor<32x64xf32>, %arg2: tensor<64xf32>, %arg3: tensor<64x32xf32>, %arg4: tensor<32xf32>, %arg5: tensor<16x32xf32>) -> (tensor<16x32xf32>, tensor<16xf32>) {
    %cst = stablehlo.constant dense<0.000000e+00> : tensor<16x64xf32>
    %cst_0 = stablehlo.constant dense<0.000000e+00> : tensor<f32>
    %0 = stablehlo.dot %arg0, %arg1, precision = [DEFAULT, DEFAULT] : (tensor<16x32xf32>, tensor<32x64xf32>) -> tensor<16x64xf32>
    %1 = stablehlo.broadcast_in_dim %arg2, dims = [1] : (tensor<64xf32>) -> tensor<16x64xf32>
    %2 = stablehlo.add %0, %1 : tensor<16x64xf32>
    %3 = stablehlo.maximum %2, %cst : tensor<16x64xf32>
    %4 = stablehlo.dot %3, %arg3, precision = [DEFAULT, DEFAULT] : (tensor<16x64xf32>, tensor<64x32xf32>) -> tensor<16x32xf32>
    %5 = stablehlo.broadcast_in_dim %arg4, dims = [1] : (tensor<32xf32>) -> tensor<16x32xf32>
    %6 = stablehlo.add %4, %5 : tensor<16x32xf32>
    %7 = stablehlo.add %6, %arg5 : tensor<16x32xf32>
    %8 = stablehlo.reduce(%7 init: %cst_0) applies stablehlo.add across dimensions = [1] : (tensor<16x32xf32>, tensor<f32>) -> tensor<16xf32>
    return %7, %8 : tensor<16x32xf32>, tensor<16xf32>
  }
}
