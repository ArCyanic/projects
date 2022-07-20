from django.db import models


# Create your models here.


class PatentsTrendOverYears(models.Model):  # 历年专利数动向图
    # 以下为自定义项
    DateType = models.CharField(max_length=30, null=True)   # 申请日、公开日
    date = models.CharField(max_length=30, null=True)   # 日期
    PatentType = models.CharField(max_length=30, null=True)   # 专利类型
    DeleteStatus = models.IntegerField(null=True)  # 软删除 0为不删除 1为删除


class OpenYearMonthDistribution(models.Model):  # 公开年月分布图
    # 以下为自定义项
    date = models.CharField(max_length=30, null=True)   # 日期
    PatentType = models.CharField(max_length=30, null=True)   # 专利类型
    DeleteStatus = models.IntegerField(null=True)  # 软删除 0为不删除 1为删除


class PatentLifeCycle(models.Model):  # 专利生命周期图
    # 以下为自定义项
    LifeCycleType = models.CharField(max_length=30, null=True)   # 生命周期类型
    ApplyTime = models.CharField(max_length=30, null=True)   # 申请时间
    ApplicantsNumber = models.IntegerField(null=True)   # 申请人数量
    PatentNumber = models.IntegerField(null=True)   # 专利数量
    DeleteStatus = models.IntegerField(null=True)  # 软删除 0为不删除 1为删除


class TechnicalEfficacyTrends(models.Model):  # 技术功效趋势图
    # 以下为自定义项
    TechnicalEfficacy = models.CharField(max_length=30, null=True)   # 技术功效
    year = models.IntegerField(null=True)   # 年份
    value = models.IntegerField(null=True)   # 数值
    DeleteStatus = models.IntegerField(null=True)  # 软删除 0为不删除 1为删除
