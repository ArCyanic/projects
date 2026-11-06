#map = affine_map<(d0, d1) -> (d1)>
#map1 = affine_map<(d0, d1) -> (d0, d1)>
#map2 = affine_map<(d0, d1) -> (d0)>
module @residual_mlp {
  func.func @main(%arg0: tensor<16x32xf32>, %arg1: tensor<32x64xf32>, %arg2: tensor<64xf32>, %arg3: tensor<64x32xf32>, %arg4: tensor<32xf32>, %arg5: tensor<16x32xf32>) -> (tensor<16x32xf32>, tensor<16xf32>) {
    %cst = arith.constant 0.000000e+00 : f32
    %0 = tensor.empty() : tensor<16x64xf32>
    %1 = linalg.fill ins(%cst : f32) outs(%0 : tensor<16x64xf32>) -> tensor<16x64xf32>
    %2 = linalg.matmul ins(%arg0, %arg1 : tensor<16x32xf32>, tensor<32x64xf32>) outs(%1 : tensor<16x64xf32>) -> tensor<16x64xf32>
    %3 = tensor.empty() : tensor<16x64xf32>
    %4 = linalg.generic {indexing_maps = [#map, #map1], iterator_types = ["parallel", "parallel"]} ins(%arg2 : tensor<64xf32>) outs(%3 : tensor<16x64xf32>) {
    ^bb0(%in: f32, %out: f32):
      linalg.yield %in : f32
    } -> tensor<16x64xf32>
    %5 = tensor.empty() : tensor<16x64xf32>
    %6 = linalg.generic {indexing_maps = [#map1, #map1, #map1], iterator_types = ["parallel", "parallel"]} ins(%2, %4 : tensor<16x64xf32>, tensor<16x64xf32>) outs(%5 : tensor<16x64xf32>) {
    ^bb0(%in: f32, %in_0: f32, %out: f32):
      %21 = arith.addf %in, %in_0 : f32
      linalg.yield %21 : f32
    } -> tensor<16x64xf32>
    %7 = tensor.empty() : tensor<16x64xf32>
    %8 = linalg.generic {indexing_maps = [#map1, #map1], iterator_types = ["parallel", "parallel"]} ins(%6 : tensor<16x64xf32>) outs(%7 : tensor<16x64xf32>) {
    ^bb0(%in: f32, %out: f32):
      %21 = arith.maximumf %in, %cst : f32
      linalg.yield %21 : f32
    } -> tensor<16x64xf32>
    %9 = tensor.empty() : tensor<16x32xf32>
    %10 = linalg.fill ins(%cst : f32) outs(%9 : tensor<16x32xf32>) -> tensor<16x32xf32>
    %11 = linalg.matmul ins(%8, %arg3 : tensor<16x64xf32>, tensor<64x32xf32>) outs(%10 : tensor<16x32xf32>) -> tensor<16x32xf32>
    %12 = tensor.empty() : tensor<16x32xf32>
    %13 = linalg.generic {indexing_maps = [#map, #map1], iterator_types = ["parallel", "parallel"]} ins(%arg4 : tensor<32xf32>) outs(%12 : tensor<16x32xf32>) {
    ^bb0(%in: f32, %out: f32):
      linalg.yield %in : f32
    } -> tensor<16x32xf32>
    %14 = tensor.empty() : tensor<16x32xf32>
    %15 = linalg.generic {indexing_maps = [#map1, #map1, #map1], iterator_types = ["parallel", "parallel"]} ins(%11, %13 : tensor<16x32xf32>, tensor<16x32xf32>) outs(%14 : tensor<16x32xf32>) {
    ^bb0(%in: f32, %in_0: f32, %out: f32):
      %21 = arith.addf %in, %in_0 : f32
      linalg.yield %21 : f32
    } -> tensor<16x32xf32>
    %16 = tensor.empty() : tensor<16x32xf32>
    %17 = linalg.generic {indexing_maps = [#map1, #map1, #map1], iterator_types = ["parallel", "parallel"]} ins(%15, %arg5 : tensor<16x32xf32>, tensor<16x32xf32>) outs(%16 : tensor<16x32xf32>) {
    ^bb0(%in: f32, %in_0: f32, %out: f32):
      %21 = arith.addf %in, %in_0 : f32
      linalg.yield %21 : f32
    } -> tensor<16x32xf32>
    %18 = tensor.empty() : tensor<16xf32>
    %19 = linalg.fill ins(%cst : f32) outs(%18 : tensor<16xf32>) -> tensor<16xf32>
    %20 = linalg.generic {indexing_maps = [#map1, #map2], iterator_types = ["parallel", "reduction"]} ins(%17 : tensor<16x32xf32>) outs(%19 : tensor<16xf32>) {
    ^bb0(%in: f32, %out: f32):
      %21 = arith.addf %out, %in : f32
      linalg.yield %21 : f32
    } -> tensor<16xf32>
    return %17, %20 : tensor<16x32xf32>, tensor<16xf32>
  }
}
