#config = #iree_codegen.lowering_config<tile_sizes = [[16, 64], [1, 4], [0, 0, 4]]>
#config1 = #iree_codegen.lowering_config<tile_sizes = [[16, 32], [1, 4], [0, 0, 4]]>
#config2 = #iree_codegen.lowering_config<tile_sizes = [[1], [0, 32]]>
#executable_target_metal_msl_fb = #hal.executable.target<"metal-spirv", "metal-msl-fb", {iree_codegen.target_info = #iree_gpu.target<arch = "apple", features = "spirv:v1.3,cap:Shader", wgp = <compute = fp32|fp16|int64|int32|int16|int8, storage = b64|b32|b16|b8, subgroup = shuffle|arithmetic, dot = dp4xi8toi32, subgroup_size_choices = [32], max_workgroup_sizes = [1024, 1024, 1024], max_thread_count_per_workgroup = 1024, max_workgroup_memory_bytes = 32768, max_workgroup_counts = [65535, 65535, 65535]>>}>
#map = affine_map<(d0, d1, d2) -> (d0, d2)>
#map1 = affine_map<(d0, d1, d2) -> (d2, d1)>
#map2 = affine_map<(d0, d1, d2) -> (d0, d1)>
#map3 = affine_map<(d0, d1) -> (d0, d1)>
#map4 = affine_map<(d0, d1) -> (d1)>
#map5 = affine_map<(d0, d1) -> (d0)>
#pipeline_layout = #hal.pipeline.layout<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>
#pipeline_layout1 = #hal.pipeline.layout<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>
#pipeline_layout2 = #hal.pipeline.layout<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>
#translation = #iree_codegen.translation_info<pipeline = SPIRVBaseVectorize workgroup_size = [16, 16, 1]>
#translation1 = #iree_codegen.translation_info<pipeline = SPIRVBaseVectorize workgroup_size = [8, 16, 1]>
#translation2 = #iree_codegen.translation_info<pipeline = SPIRVSubgroupReduce workgroup_size = [32, 1, 1]>
#device_target_metal = #hal.device.target<"metal", [#executable_target_metal_msl_fb]> : !hal.device
module @residual_mlp attributes {stream.affinity.default = #hal.device.affinity<@__device_0>} {
  util.global private @__device_0 = #device_target_metal
  hal.executable private @main_dispatch_0 {
    hal.executable.variant public @metal_msl_fb target(#executable_target_metal_msl_fb) {
      hal.executable.export public @main_dispatch_0_matmul_16x64x32_f32 ordinal(0) layout(#pipeline_layout) count(%arg0: !hal.device) -> (index, index, index) {
        %x, %y, %z = iree_tensor_ext.dispatch.workgroup_count_from_slice()
        hal.return %x, %y, %z : index, index, index
      }
      builtin.module {
        func.func @main_dispatch_0_matmul_16x64x32_f32() attributes {translation_info = #translation} {
          %cst = arith.constant 0.000000e+00 : f32
          %c0 = arith.constant 0 : index
          %0 = hal.interface.binding.subspan layout(#pipeline_layout) binding(0) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>>
          %1 = hal.interface.binding.subspan layout(#pipeline_layout) binding(1) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<32x64xf32>>
          %2 = hal.interface.binding.subspan layout(#pipeline_layout) binding(2) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<64xf32>>
          %3 = hal.interface.binding.subspan layout(#pipeline_layout) binding(3) alignment(64) offset(%c0) flags(Indirect) : !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x64xf32>>
          %4 = iree_tensor_ext.dispatch.tensor.load %0, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>> -> tensor<16x32xf32>
          %5 = iree_tensor_ext.dispatch.tensor.load %1, offsets = [0, 0], sizes = [32, 64], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<32x64xf32>> -> tensor<32x64xf32>
          %6 = iree_tensor_ext.dispatch.tensor.load %2, offsets = [0], sizes = [64], strides = [1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<64xf32>> -> tensor<64xf32>
          %7 = tensor.empty() : tensor<16x64xf32>
          %8 = linalg.fill ins(%cst : f32) outs(%7 : tensor<16x64xf32>) -> tensor<16x64xf32>
          %9 = linalg.generic {indexing_maps = [#map, #map1, #map2], iterator_types = ["parallel", "parallel", "reduction"]} ins(%4, %5 : tensor<16x32xf32>, tensor<32x64xf32>) outs(%8 : tensor<16x64xf32>) attrs =  {lowering_config = #config} {
          ^bb0(%in: f32, %in_0: f32, %out: f32):
            %11 = arith.mulf %in, %in_0 : f32
            %12 = arith.addf %out, %11 : f32
            linalg.yield %12 : f32
          } -> tensor<16x64xf32>
          %10 = linalg.generic {indexing_maps = [#map3, #map4, #map3], iterator_types = ["parallel", "parallel"]} ins(%9, %6 : tensor<16x64xf32>, tensor<64xf32>) outs(%7 : tensor<16x64xf32>) {
          ^bb0(%in: f32, %in_0: f32, %out: f32):
            %11 = arith.addf %in, %in_0 : f32
            %12 = arith.maximumf %11, %cst : f32
            linalg.yield %12 : f32
          } -> tensor<16x64xf32>
          iree_tensor_ext.dispatch.tensor.store %10, %3, offsets = [0, 0], sizes = [16, 64], strides = [1, 1] : tensor<16x64xf32> -> !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x64xf32>>
          return
        }
      }
    }
  }
  hal.executable private @main_dispatch_1 {
    hal.executable.variant public @metal_msl_fb target(#executable_target_metal_msl_fb) {
      hal.executable.export public @main_dispatch_1_matmul_16x32x64_f32 ordinal(0) layout(#pipeline_layout1) count(%arg0: !hal.device) -> (index, index, index) {
        %x, %y, %z = iree_tensor_ext.dispatch.workgroup_count_from_slice()
        hal.return %x, %y, %z : index, index, index
      }
      builtin.module {
        func.func @main_dispatch_1_matmul_16x32x64_f32() attributes {translation_info = #translation1} {
          %cst = arith.constant 0.000000e+00 : f32
          %c0 = arith.constant 0 : index
          %0 = hal.interface.binding.subspan layout(#pipeline_layout1) binding(0) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x64xf32>>
          %1 = hal.interface.binding.subspan layout(#pipeline_layout1) binding(1) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<64x32xf32>>
          %2 = hal.interface.binding.subspan layout(#pipeline_layout1) binding(2) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<32xf32>>
          %3 = hal.interface.binding.subspan layout(#pipeline_layout1) binding(3) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>>
          %4 = hal.interface.binding.subspan layout(#pipeline_layout1) binding(4) alignment(64) offset(%c0) flags(Indirect) : !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x32xf32>>
          %5 = iree_tensor_ext.dispatch.tensor.load %0, offsets = [0, 0], sizes = [16, 64], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x64xf32>> -> tensor<16x64xf32>
          %6 = iree_tensor_ext.dispatch.tensor.load %1, offsets = [0, 0], sizes = [64, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<64x32xf32>> -> tensor<64x32xf32>
          %7 = iree_tensor_ext.dispatch.tensor.load %2, offsets = [0], sizes = [32], strides = [1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<32xf32>> -> tensor<32xf32>
          %8 = iree_tensor_ext.dispatch.tensor.load %3, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>> -> tensor<16x32xf32>
          %9 = tensor.empty() : tensor<16x32xf32>
          %10 = linalg.fill ins(%cst : f32) outs(%9 : tensor<16x32xf32>) -> tensor<16x32xf32>
          %11 = linalg.generic {indexing_maps = [#map, #map1, #map2], iterator_types = ["parallel", "parallel", "reduction"]} ins(%5, %6 : tensor<16x64xf32>, tensor<64x32xf32>) outs(%10 : tensor<16x32xf32>) attrs =  {lowering_config = #config1} {
          ^bb0(%in: f32, %in_0: f32, %out: f32):
            %13 = arith.mulf %in, %in_0 : f32
            %14 = arith.addf %out, %13 : f32
            linalg.yield %14 : f32
          } -> tensor<16x32xf32>
          %12 = linalg.generic {indexing_maps = [#map3, #map4, #map3, #map3], iterator_types = ["parallel", "parallel"]} ins(%11, %7, %8 : tensor<16x32xf32>, tensor<32xf32>, tensor<16x32xf32>) outs(%9 : tensor<16x32xf32>) {
          ^bb0(%in: f32, %in_0: f32, %in_1: f32, %out: f32):
            %13 = arith.addf %in, %in_0 : f32
            %14 = arith.addf %13, %in_1 : f32
            linalg.yield %14 : f32
          } -> tensor<16x32xf32>
          iree_tensor_ext.dispatch.tensor.store %12, %4, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : tensor<16x32xf32> -> !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x32xf32>>
          return
        }
      }
    }
  }
  hal.executable private @main_dispatch_2 {
    hal.executable.variant public @metal_msl_fb target(#executable_target_metal_msl_fb) {
      hal.executable.export public @main_dispatch_2_reduction_16x32_f32 ordinal(0) layout(#pipeline_layout2) count(%arg0: !hal.device) -> (index, index, index) {
        %x, %y, %z = iree_tensor_ext.dispatch.workgroup_count_from_slice()
        hal.return %x, %y, %z : index, index, index
      }
      builtin.module {
        func.func @main_dispatch_2_reduction_16x32_f32() attributes {translation_info = #translation2} {
          %cst = arith.constant 0.000000e+00 : f32
          %c0 = arith.constant 0 : index
          %c2048 = arith.constant 2048 : index
          %0 = hal.interface.binding.subspan layout(#pipeline_layout2) binding(0) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>>
          %1 = hal.interface.binding.subspan layout(#pipeline_layout2) binding(1) alignment(64) offset(%c2048) flags(Indirect) : !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16xf32>>
          %2 = iree_tensor_ext.dispatch.tensor.load %0, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>> -> tensor<16x32xf32>
          %3 = tensor.empty() : tensor<16xf32>
          %4 = linalg.fill {lowering_config = #config2} ins(%cst : f32) outs(%3 : tensor<16xf32>) -> tensor<16xf32>
          %5 = linalg.generic {indexing_maps = [#map3, #map5], iterator_types = ["parallel", "reduction"]} ins(%2 : tensor<16x32xf32>) outs(%4 : tensor<16xf32>) attrs =  {lowering_config = #config2} {
          ^bb0(%in: f32, %out: f32):
            %6 = arith.addf %out, %in : f32
            linalg.yield %6 : f32
          } -> tensor<16xf32>
          iree_tensor_ext.dispatch.tensor.store %5, %1, offsets = [0], sizes = [16], strides = [1] : tensor<16xf32> -> !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16xf32>>
          return
        }
      }
    }
  }
  util.func public @main(%arg0: !hal.buffer_view, %arg1: !hal.buffer_view, %arg2: !hal.buffer_view, %arg3: !hal.buffer_view, %arg4: !hal.buffer_view, %arg5: !hal.buffer_view) -> (!hal.buffer_view, !hal.buffer_view) attributes {iree.abi.stub, iree.reflection = {iree.abi.declaration = "sync func @main(%input0: tensor<16x32xf32>, %input1: tensor<32x64xf32>, %input2: tensor<64xf32>, %input3: tensor<64x32xf32>, %input4: tensor<32xf32>, %input5: tensor<16x32xf32>) -> (%output0: tensor<16x32xf32>, %output1: tensor<16xf32>)"}} {
    %c0 = arith.constant 0 : index
    %c2112 = arith.constant 2112 : index
    %c4096 = arith.constant 4096 : index
    %c128 = arith.constant 128 : index
    %c256 = arith.constant 256 : index
    %c8192 = arith.constant 8192 : index
    %c2048 = arith.constant 2048 : index
    %c64 = arith.constant 64 : index
    %c32 = arith.constant 32 : index
    %c16 = arith.constant 16 : index
    %element_type_f32 = hal.element_type<f32> : i32
    %dense_row_major = hal.encoding_type<dense_row_major> : i32
    hal.buffer_view.assert<%arg0 : !hal.buffer_view> message("input0") shape([%c16, %c32]) type(%element_type_f32) encoding(%dense_row_major)
    %0 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg0 : !hal.buffer_view -> tensor<16x32xf32> in !stream.resource<external>{%c2048}
    hal.buffer_view.assert<%arg1 : !hal.buffer_view> message("input1") shape([%c32, %c64]) type(%element_type_f32) encoding(%dense_row_major)
    %1 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg1 : !hal.buffer_view -> tensor<32x64xf32> in !stream.resource<external>{%c8192}
    hal.buffer_view.assert<%arg2 : !hal.buffer_view> message("input2") shape([%c64]) type(%element_type_f32) encoding(%dense_row_major)
    %2 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg2 : !hal.buffer_view -> tensor<64xf32> in !stream.resource<external>{%c256}
    hal.buffer_view.assert<%arg3 : !hal.buffer_view> message("input3") shape([%c64, %c32]) type(%element_type_f32) encoding(%dense_row_major)
    %3 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg3 : !hal.buffer_view -> tensor<64x32xf32> in !stream.resource<external>{%c8192}
    hal.buffer_view.assert<%arg4 : !hal.buffer_view> message("input4") shape([%c32]) type(%element_type_f32) encoding(%dense_row_major)
    %4 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg4 : !hal.buffer_view -> tensor<32xf32> in !stream.resource<external>{%c128}
    hal.buffer_view.assert<%arg5 : !hal.buffer_view> message("input5") shape([%c16, %c32]) type(%element_type_f32) encoding(%dense_row_major)
    %5 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg5 : !hal.buffer_view -> tensor<16x32xf32> in !stream.resource<external>{%c2048}
    %result, %result_timepoint = stream.resource.alloca uninitialized on(#hal.device.affinity<@__device_0>) : !stream.resource<external>{%c2112} => !stream.timepoint
    %result_0, %result_timepoint_1 = stream.resource.alloca uninitialized on(#hal.device.affinity<@__device_0>) : !stream.resource<transient>{%c4096} => !stream.timepoint
    %6 = stream.timepoint.join max(%result_timepoint, %result_timepoint_1) => !stream.timepoint
    %7 = stream.cmd.execute on(#hal.device.affinity<@__device_0>) await(%6) => with(%0 as %arg6: !stream.resource<external>{%c2048}, %1 as %arg7: !stream.resource<external>{%c8192}, %2 as %arg8: !stream.resource<external>{%c256}, %3 as %arg9: !stream.resource<external>{%c8192}, %4 as %arg10: !stream.resource<external>{%c128}, %5 as %arg11: !stream.resource<external>{%c2048}, %result as %arg12: !stream.resource<external>{%c2112}, %result_0 as %arg13: !stream.resource<transient>{%c4096}) {
      stream.cmd.dispatch @main_dispatch_0::@metal_msl_fb::@main_dispatch_0_matmul_16x64x32_f32 {
        ro %arg6[%c0 for %c2048] : !stream.resource<external>{%c2048},
        ro %arg7[%c0 for %c8192] : !stream.resource<external>{%c8192},
        ro %arg8[%c0 for %c256] : !stream.resource<external>{%c256},
        wo %arg13[%c0 for %c4096] : !stream.resource<transient>{%c4096}
      }
      stream.cmd.dispatch @main_dispatch_1::@metal_msl_fb::@main_dispatch_1_matmul_16x32x64_f32 {
        ro %arg13[%c0 for %c4096] : !stream.resource<transient>{%c4096},
        ro %arg9[%c0 for %c8192] : !stream.resource<external>{%c8192},
        ro %arg10[%c0 for %c128] : !stream.resource<external>{%c128},
        ro %arg11[%c0 for %c2048] : !stream.resource<external>{%c2048},
        wo %arg12[%c0 for %c2112] : !stream.resource<external>{%c2112}
      }
      stream.cmd.dispatch @main_dispatch_2::@metal_msl_fb::@main_dispatch_2_reduction_16x32_f32 {
        ro %arg12[%c0 for %c2112] : !stream.resource<external>{%c2112},
        wo %arg12[%c0 for %c2112] : !stream.resource<external>{%c2112}
      }
    } => !stream.timepoint
    %8 = stream.resource.dealloca on(#hal.device.affinity<@__device_0>) await(%7) => %result_0 : !stream.resource<transient>{%c4096} => !stream.timepoint
    %9 = stream.timepoint.await %8 => %result : !stream.resource<external>{%c2112}
    %10 = stream.resource.subview %9[%c0] : !stream.resource<external>{%c2112} -> !stream.resource<external>{%c2048}
    %11 = stream.resource.subview %9[%c2048] : !stream.resource<external>{%c2112} -> !stream.resource<external>{%c64}
    %12 = stream.tensor.export on(#hal.device.affinity<@__device_0>) %10 : tensor<16x32xf32> in !stream.resource<external>{%c2048} -> !hal.buffer_view
    %13 = stream.tensor.export on(#hal.device.affinity<@__device_0>) %11 : tensor<16xf32> in !stream.resource<external>{%c64} -> !hal.buffer_view
    util.return %12, %13 : !hal.buffer_view, !hal.buffer_view
  }
}
