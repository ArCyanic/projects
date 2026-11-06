spirv.module Logical GLSL450 requires #spirv.vce<v1.3, [Shader, GroupNonUniformArithmetic, Matrix, GroupNonUniform], [SPV_KHR_storage_buffer_storage_class]> {
  spirv.GlobalVariable @__builtin__WorkgroupId__ built_in("WorkgroupId") : !spirv.ptr<vector<3xi32>, Input>
  spirv.GlobalVariable @__builtin__LocalInvocationId__ built_in("LocalInvocationId") : !spirv.ptr<vector<3xi32>, Input>
  spirv.GlobalVariable @__resource_var_0_0_ bind(0, 0) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>
  spirv.GlobalVariable @__resource_var_0_1_ bind(0, 1) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>
  spirv.func @main_dispatch_2_reduction_16x32_f32() "None" {
    %cst512_i32 = spirv.Constant 512 : i32
    %cst32_i32 = spirv.Constant 32 : i32
    %cst0_i32 = spirv.Constant 0 : i32
    %cst_f32 = spirv.Constant 0.000000e+00 : f32
    %__resource_var_0_0__addr = spirv.mlir.addressof @__resource_var_0_0_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>
    %__resource_var_0_1__addr = spirv.mlir.addressof @__resource_var_0_1_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>
    %__builtin__LocalInvocationId___addr = spirv.mlir.addressof @__builtin__LocalInvocationId__ : !spirv.ptr<vector<3xi32>, Input>
    %0 = spirv.Load "Input" %__builtin__LocalInvocationId___addr : vector<3xi32>
    %1 = spirv.CompositeExtract %0[0 : i32] : vector<3xi32>
    %2 = spirv.IEqual %1, %cst0_i32 : i32
    %__builtin__WorkgroupId___addr = spirv.mlir.addressof @__builtin__WorkgroupId__ : !spirv.ptr<vector<3xi32>, Input>
    %3 = spirv.Load "Input" %__builtin__WorkgroupId___addr : vector<3xi32>
    %4 = spirv.CompositeExtract %3[0 : i32] : vector<3xi32>
    %5 = spirv.IMul %4, %cst32_i32 : i32
    %6 = spirv.IAdd %1, %5 : i32
    %7 = spirv.AccessChain %__resource_var_0_0__addr[%cst0_i32, %6] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<f32, StorageBuffer>
    %8 = spirv.Load "StorageBuffer" %7 : f32
    %9 = spirv.FAdd %8, %cst_f32 : f32
    %10 = spirv.GroupNonUniformFAdd <Subgroup> <Reduce> %9 : f32 -> f32
    %11 = spirv.FAdd %10, %cst_f32 : f32
    spirv.mlir.selection {
      spirv.BranchConditional %2, ^bb1, ^bb2
    ^bb1:  // pred: ^bb0
      %12 = spirv.IAdd %4, %cst512_i32 : i32
      %13 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %12] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<f32, StorageBuffer>
      spirv.Store "StorageBuffer" %13, %11 : f32
      spirv.Branch ^bb2
    ^bb2:  // 2 preds: ^bb0, ^bb1
      spirv.mlir.merge
    }
    spirv.Return
  }
  spirv.EntryPoint "GLCompute" @main_dispatch_2_reduction_16x32_f32, @__builtin__LocalInvocationId__, @__builtin__WorkgroupId__
  spirv.ExecutionMode @main_dispatch_2_reduction_16x32_f32 "LocalSize", 32, 1, 1
}