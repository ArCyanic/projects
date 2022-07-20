import json
from django.db.models import Max, Min
from django.http import JsonResponse
from qipvp_server.settings import DEBUG

from trend_analysis.models import TechnicalEfficacyTrends, PatentsTrendOverYears, PatentLifeCycle, \
    OpenYearMonthDistribution


# Create your views here.
def get_patents_trend_over_years(request):
    result_response = {
        'status': 0,
        'msg': '操作失败',
    }
    try:
        # 筛选数据库 按date升序排列
        searchParams = {
            'DeleteStatus': 0,
        }
        results = PatentsTrendOverYears.objects.filter(**searchParams).order_by('date')
        # 获取前端参数
        requestData = request.POST
        showType = requestData.get('showType', 'year')
        # 构造时间数组 x轴标签date__max': '20210420', 'date__min
        dates = []
        maxMinDate = results.aggregate(Max('date'), Min('date'))
        maxDate = maxMinDate.get('date__max', '20200101')
        minDate = maxMinDate.get('date__min', '20200101')
        if showType == 'year':
            maxYear = int(maxDate[0:4])
            minYear = int(minDate[0:4])
            for year in range(minYear, maxYear + 1):
                dates.append(str(year))
        elif showType == 'month':
            maxMonth = int(maxDate[0:6])
            minMonth = int(minDate[0:6])
            for month in range(minMonth, maxMonth + 1):
                if (month % 100 >= 13 or month % 100 == 0):
                    continue
                dates.append(str(month))
        # 获取需要的数据 发明 实用新型 外观设计 invention  | Utility model  |  Appearance design
        records = {
            'aInvention': [0 for i in range(0, len(dates))],
            'aUtilityModel': [0 for i in range(0, len(dates))],
            'aAppearanceDesign': [0 for i in range(0, len(dates))],
            'aSum': [0 for i in range(0, len(dates))],
            'pInvention': [0 for i in range(0, len(dates))],
            'pUtilityModel': [0 for i in range(0, len(dates))],
            'pAppearanceDesign': [0 for i in range(0, len(dates))],
            'pSum': [0 for i in range(0, len(dates))],
        }
        for result in results:
            DateType = result.DateType
            date = result.date
            PatentType = result.PatentType
            index = 0
            if showType == 'year':
                index = dates.index(date[0:4])
            elif showType == 'month':
                index = dates.index(date[0:6])
            if '申请日' in DateType:
                if '发明' in PatentType:
                    records['aInvention'][index] += 1
                elif '实用' in PatentType:
                    records['aUtilityModel'][index] += 1
                elif '外观' in PatentType:
                    records['aAppearanceDesign'][index] += 1
                records['aSum'][index] += 1
            elif '公开日' in DateType:
                if '发明' in PatentType:
                    records['pInvention'][index] += 1
                elif '实用' in PatentType:
                    records['pUtilityModel'][index] += 1
                elif '外观' in PatentType:
                    records['pAppearanceDesign'][index] += 1
                records['pSum'][index] += 1
        # 键对应的中文名称
        transformToCn = {
            'aInvention': '申请日-发明',
            'aUtilityModel': '申请日-实用新型',
            'aAppearanceDesign': '申请日-外观设计',
            'aSum': '申请日-总计',
            'pInvention': '公开日-发明',
            'pUtilityModel': '公开日-实用新型',
            'pAppearanceDesign': '公开日-外观设计',
            'pSum': '公开日-总计',
        }
        result_response['dates'] = dates
        result_response['records'] = records
        result_response['transformToCn'] = transformToCn
        result_response['status'] = 1
        result_response['msg'] = '获取成功'
    except Exception as error:
        if DEBUG:
            result_response['msg'] = '获取失败' + str(error)
        else:
            result_response['msg'] = '获取失败'
    return JsonResponse(result_response)


def get_open_year_month_distribution(request):
    result_response = {
        'status': 0,
        'msg': '操作失败',
    }
    try:
        # 筛选数据库 按date升序排列
        searchParams = {
            'DeleteStatus': 0,
        }
        results = OpenYearMonthDistribution.objects.filter(**searchParams).order_by('date')
        # 获取前端参数
        requestData = request.POST
        showType = requestData.get('showType', 'year')
        # 构造时间数组 x轴标签
        years = []
        months = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月']
        maxMinDate = results.aggregate(Max('date'), Min('date'))
        maxDate = maxMinDate.get('date__max', '20200101')
        minDate = maxMinDate.get('date__min', '20200101')
        maxYear = int(maxDate[0:4])
        minYear = int(minDate[0:4])
        for year in range(minYear, maxYear + 1):
            years.append(str(year))
        # 获取需要的数据 发明 实用新型 外观设计 invention  | Utility model  |  Appearance design
        records = {}
        for result in results:
            month = result.date[0:6]
            if records.get(month, 0):
                records[month] += 1
            else:
                records[month] = 1
        recordsFinal = []
        for key in records:
            year = key[0:4]
            month = int(key[4:6])
            recordsFinal.append([
                years.index(year),
                month - 1,
                records[key],
            ])
        result_response['years'] = years
        result_response['months'] = months
        result_response['recordsFinal'] = recordsFinal
        result_response['status'] = 1
        result_response['msg'] = '获取成功'
    except Exception as error:
        if DEBUG:
            result_response['msg'] = '获取失败' + str(error)
        else:
            result_response['msg'] = '获取失败'
    return JsonResponse(result_response)


def get_patent_life_cycle(request):
    result_response = {
        'status': 0,
        'msg': '操作失败',
    }
    try:
        searchParams = {
            'DeleteStatus': 0,
        }
        results = PatentLifeCycle.objects.filter(**searchParams).order_by('ApplyTime')
        # 获取横纵坐标标签 Domestic and international
        years = []
        domestic = []
        international = []
        # 获取最终格式的数据
        for result in results:
            LifeCycleType = result.LifeCycleType
            ApplyTime = result.ApplyTime
            ApplicantsNumber = result.ApplicantsNumber
            PatentNumber = result.PatentNumber
            if ApplyTime not in years:
                years.append(ApplyTime)
            if '国际' in LifeCycleType:
                international.append([
                    PatentNumber,
                    ApplicantsNumber
                ])
            else:
                domestic.append([
                    PatentNumber,
                    ApplicantsNumber
                ])
        result_response['years'] = years
        result_response['domestic'] = domestic
        result_response['international'] = international
        result_response['status'] = 1
        result_response['msg'] = '获取成功'
    except Exception as error:
        if DEBUG:
            result_response['msg'] = '获取失败' + str(error)
        else:
            result_response['msg'] = '获取失败'
    return JsonResponse(result_response)


def get_technical_efficacy_trends(request):
    result_response = {
        'status': 0,
        'msg': '操作失败',
    }
    try:
        # requestData = request.POST
        # print(requestData.get('lastName', 'dasjhdk'))
        searchParams = {
            'DeleteStatus': 0,
        }
        results = TechnicalEfficacyTrends.objects.filter(**searchParams).order_by('year')
        # 获取横纵坐标标签
        years = []
        effects = []
        records = []
        for result in results:
            TechnicalEfficacy = result.TechnicalEfficacy
            year = result.year
            value = result.value
            if year not in years:
                years.append(year)
            if TechnicalEfficacy not in effects:
                effects.append(TechnicalEfficacy)
            records.append([
                years.index(year),
                effects.index(TechnicalEfficacy),
                value
            ])
        result_response['years'] = years
        result_response['effects'] = effects
        result_response['records'] = records
        result_response['status'] = 1
        result_response['msg'] = '获取成功'
    except Exception as error:
        if DEBUG:
            result_response['msg'] = '获取失败' + str(error)
        else:
            result_response['msg'] = '获取失败'
    return JsonResponse(result_response)
