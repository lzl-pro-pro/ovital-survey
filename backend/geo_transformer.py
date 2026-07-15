"""坐标转换模块 - CAD局部坐标 ↔ WGS-84 GPS坐标"""

import json
import numpy as np
from backend.data_manager import get_project, update_project


def set_reference_points(project_id, cad_points, gps_points):
    """
    设置参考点对，计算仿射变换参数

    Args:
        project_id: 项目ID
        cad_points: CAD坐标列表 [(x1, y1), (x2, y2), ...]
        gps_points: GPS坐标列表 [(lng1, lat1), (lng2, lat2), ...]

    Returns:
        dict: 仿射变换参数 {"a": ..., "b": ..., "c": ..., "d": ..., "e": ..., "f": ...}
    """
    if len(cad_points) < 2 or len(gps_points) < 2:
        raise ValueError("至少需要2个参考点对")

    if len(cad_points) != len(gps_points):
        raise ValueError("CAD点和GPS点数量必须一致")

    # 提取坐标
    x = np.array([p[0] for p in cad_points])
    y = np.array([p[1] for p in cad_points])
    lng = np.array([p[0] for p in gps_points])
    lat = np.array([p[1] for p in gps_points])

    # 检查参考点不共线
    if len(cad_points) >= 3:
        # 简单共线检测
        vectors = []
        for i in range(1, len(cad_points)):
            v = (cad_points[i][0] - cad_points[0][0],
                 cad_points[i][1] - cad_points[0][1])
            vectors.append(v)
        # 检测是否所有向量都平行
        if len(vectors) >= 2:
            cross = vectors[0][0] * vectors[1][1] - vectors[0][1] * vectors[1][0]
            if abs(cross) < 1e-10:
                raise ValueError("参考点共线或过于集中，无法计算变换参数")

    # 最小二乘法求解仿射变换
    # lng = a*x + b*y + c
    # lat = d*x + e*y + f
    n = len(cad_points)
    A = np.column_stack([x, y, np.ones(n)])

    try:
        # 解 lng = a*x + b*y + c
        params_lng, residuals_lng, rank_lng, s_lng = np.linalg.lstsq(
            A, lng, rcond=None
        )
        a, b, c = params_lng

        # 解 lat = d*x + e*y + f
        params_lat, residuals_lat, rank_lat, s_lat = np.linalg.lstsq(
            A, lat, rcond=None
        )
        d, e, f = params_lat
    except np.linalg.LinAlgError:
        raise ValueError("矩阵求解失败，请检查参考点坐标")

    params = {
        "a": float(a), "b": float(b), "c": float(c),
        "d": float(d), "e": float(e), "f": float(f),
    }

    # 计算残差（精度评估）
    lng_pred = a * x + b * y + c
    lat_pred = d * x + e * y + f
    lng_residual = np.abs(lng - lng_pred).max()
    lat_residual = np.abs(lat - lat_pred).max()

    params["max_lng_error"] = float(lng_residual)
    params["max_lat_error"] = float(lat_residual)

    # 保存到项目
    update_project(project_id, transform_params=params)

    return params


def cad_to_gps(cad_x, cad_y, project_id_or_params):
    """
    将CAD坐标转换为GPS坐标

    Args:
        cad_x, cad_y: CAD坐标
        project_id_or_params: 项目ID或变换参数字典

    Returns:
        tuple: (longitude, latitude)
    """
    if isinstance(project_id_or_params, dict):
        params = project_id_or_params
    else:
        project = get_project(project_id_or_params)
        if not project:
            raise ValueError("项目不存在")
        params = project.get("transform_params", {})
        if isinstance(params, str):
            import json
            params = json.loads(params)

    if not params or "a" not in params:
        raise ValueError("尚未设置坐标变换参数，请先配置参考点")

    a, b, c = params["a"], params["b"], params["c"]
    d, e, f = params["d"], params["e"], params["f"]

    lng = a * cad_x + b * cad_y + c
    lat = d * cad_x + e * cad_y + f

    return (lng, lat)


def gps_to_cad(lng, lat, project_id_or_params):
    """
    将GPS坐标转换为CAD坐标（逆变换）

    Args:
        lng, lat: GPS坐标
        project_id_or_params: 项目ID或变换参数字典

    Returns:
        tuple: (cad_x, cad_y)
    """
    if isinstance(project_id_or_params, dict):
        params = project_id_or_params
    else:
        project = get_project(project_id_or_params)
        if not project:
            raise ValueError("项目不存在")
        params = project.get("transform_params", {})
        if isinstance(params, str):
            import json
            params = json.loads(params)

    if not params or "a" not in params:
        raise ValueError("尚未设置坐标变换参数")

    a, b, c = params["a"], params["b"], params["c"]
    d, e, f = params["d"], params["e"], params["f"]

    # 逆矩阵求解
    M = np.array([[a, b], [d, e]])
    offset = np.array([c, f])
    if np.linalg.matrix_rank(M) < 2:
        raise ValueError("变换矩阵不可逆")

    target = np.array([lng, lat])
    result = np.linalg.solve(M, target - offset)

    return (float(result[0]), float(result[1]))


def batch_transform(project_id, cad_points):
    """
    批量转换CAD坐标到GPS

    Args:
        project_id: 项目ID
        cad_points: [(x1, y1), (x2, y2), ...]

    Returns:
        list: [(lng1, lat1), (lng2, lat2), ...]
    """
    project = get_project(project_id)
    if not project:
        raise ValueError("项目不存在")

    params = project.get("transform_params", {})
    if isinstance(params, str):
        import json
        params = json.loads(params)

    results = []
    for x, y in cad_points:
        results.append(cad_to_gps(x, y, params))

    return results
