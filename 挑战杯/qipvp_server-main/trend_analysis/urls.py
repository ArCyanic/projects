"""
tables URL Configuration
一级路由：office/
"""

from django.urls import path
from .views import get_patents_trend_over_years, get_open_year_month_distribution, get_patent_life_cycle, \
    get_technical_efficacy_trends

urlpatterns = [
    # 趋势分析
    path('getPatentsTrendOverYears/', get_patents_trend_over_years),  # 获取历年专利数动向图数据
    path('getOpenYearMonthDistribution/', get_open_year_month_distribution),  # 获取公开年月分布图数据
    path('getPatentLifeCycle/', get_patent_life_cycle),  # 获取专利生命周期图数据
    path('getTechnicalEfficacyTrends/', get_technical_efficacy_trends),  # 获取技术功效趋势图数据
]
