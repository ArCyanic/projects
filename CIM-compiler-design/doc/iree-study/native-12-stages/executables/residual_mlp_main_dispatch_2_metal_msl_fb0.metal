#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct _7
{
    float _m0[1];
};

struct spvDescriptorSetBuffer0
{
    device _7* _resource_var_0_0_ [[id(0)]];
    device _7* _resource_var_0_1_ [[id(1)]];
};

kernel void main_dispatch_2_reduction_16x32_f32(constant spvDescriptorSetBuffer0& spvDescriptorSet0 [[buffer(0)]], uint3 gl_WorkGroupID [[threadgroup_position_in_grid]], uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]])
{
    float _32 = simd_sum((*spvDescriptorSet0._resource_var_0_0_)._m0[gl_LocalInvocationID.x + (gl_WorkGroupID.x * 32u)] + 0.0);
    if (gl_LocalInvocationID.x == 0u)
    {
        (*spvDescriptorSet0._resource_var_0_1_)._m0[gl_WorkGroupID.x + 512u] = _32 + 0.0;
    }
}

