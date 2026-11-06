#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct _6
{
    float4 _m0[1];
};

struct spvDescriptorSetBuffer0
{
    device _6* _resource_var_0_0_ [[id(0)]];
    device _6* _resource_var_0_1_ [[id(1)]];
    device _6* _resource_var_0_2_ [[id(2)]];
    device _6* _resource_var_0_3_ [[id(3)]];
};

kernel void main_dispatch_0_matmul_16x64x32_f32(constant spvDescriptorSetBuffer0& spvDescriptorSet0 [[buffer(0)]], uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]])
{
    float4 _36;
    _36 = float4(0.0);
    float4 _31;
    for (uint _35 = 0u; int(_35) < int(32u); )
    {
        uint _40 = _35 / 4u;
        uint _41 = (gl_LocalInvocationID.y * 8u) + _40;
        uint _45 = _35 * 16u;
        uint _46 = _45 + gl_LocalInvocationID.x;
        float4 _70 = fma(float4((*spvDescriptorSet0._resource_var_0_0_)._m0[_41].w), (*spvDescriptorSet0._resource_var_0_1_)._m0[_46 + 48u], fma(float4((*spvDescriptorSet0._resource_var_0_0_)._m0[_41].z), (*spvDescriptorSet0._resource_var_0_1_)._m0[_46 + 32u], fma(float4((*spvDescriptorSet0._resource_var_0_0_)._m0[_41].y), (*spvDescriptorSet0._resource_var_0_1_)._m0[_46 + 16u], fma(float4((*spvDescriptorSet0._resource_var_0_0_)._m0[_41].x), (*spvDescriptorSet0._resource_var_0_1_)._m0[_46], _36))));
        _31 = _70;
        _35 += 4u;
        _36 = _70;
        continue;
    }
    float4 _75 = _31 + (*spvDescriptorSet0._resource_var_0_2_)._m0[gl_LocalInvocationID.x];
    (*spvDescriptorSet0._resource_var_0_3_)._m0[(gl_LocalInvocationID.y * 16u) + gl_LocalInvocationID.x] = select(select(fast::max(_75, float4(0.0)), _75, isnan(_75)), float4(0.0), isnan(float4(0.0)));
}

