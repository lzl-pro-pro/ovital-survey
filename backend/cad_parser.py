"""CAD文件解析引擎 - 支持DXF和DWG格式"""

import os
import re
import sys
import tempfile
import subprocess
import uuid
import shutil
from config import ANNOTATION_REGEX_PATTERNS, DWG_CONVERTER_PATH, ALLOWED_CAD_EXTENSIONS
from backend.data_manager import save_annotations


def parse_cad_file(file_path, project_id):
    """
    解析CAD文件，提取文本标注

    Args:
        file_path: CAD文件路径
        project_id: 项目ID

    Returns:
        dict: {annotation_count, layers, annotations, file_type, warnings}
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_CAD_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}")

    warnings = []

    # DWG文件需要先转换为DXF
    if ext == ".dwg":
        dxf_path, dwg_warning = _convert_dwg_to_dxf(file_path)
        if not dxf_path:
            raise RuntimeError(
                "无法转换DWG文件。\n\n"
                "原因：未找到DWG转DXF工具。\n\n"
                "解决方案（任选其一）：\n"
                "1.【推荐】用你的CAD软件打开DWG，另存为DXF格式，然后重新上传DXF\n"
                "2.【推荐】安装免费 ODA FileConverter：\n"
                "   https://www.opendesign.com/guestfiles/oda_file_converter\n"
                "   下载安装后，在 config.py 中设置 DWG_CONVERTER_PATH\n"
                "3. 安装 LibreDWG：pip install libredwg （仅Linux/macOS）\n"
                "4. 在命令行运行 python install_converter.py 自动安装"
            )
        if dwg_warning:
            warnings.append(dwg_warning)
        file_path = dxf_path
        warnings.append("DWG文件已自动转换为DXF格式")

    # 尝试多种编码读取DXF
    annotations = _parse_dxf_annotations(file_path, warnings)

    # 匹配工程编号
    annotations = _match_labels(annotations)

    # 保存到数据库，然后重新查询获取真实ID
    if annotations:
        count = save_annotations(project_id, annotations)
        # 重新从DB查询，确保annotation带真实ID
        from backend.data_manager import get_annotations
        db_result = get_annotations(project_id, per_page=10000)
        db_annotations = db_result["items"]
    else:
        count = 0
        db_annotations = []
        warnings.append("未从CAD文件中提取到任何文本标注。请检查：\n"
                        "1. CAD中是否有TEXT/MTEXT文字\n"
                        "2. 文字是否在模型空间（非图纸空间）\n"
                        "3. 文字图层是否被冻结/隐藏")

    # 收集图层信息
    layers = list(set(a.get("layer_name", "") for a in annotations if a.get("layer_name")))

    return {
        "annotation_count": count,
        "layer_count": len(layers),
        "layers": sorted(layers),
        "file_type": ext.lstrip("."),
        "warnings": warnings,
        "annotations": db_annotations[:10000],
        "has_more": count > 10000,
    }


def _convert_dwg_to_dxf(dwg_path):
    """
    将DWG文件转换为DXF，返回 (dxf_path, warning_message)

    按优先级尝试：
    1. AutoCAD COM自动化
    2. ODA FileConverter
    3. LibreDWG dwg2dxf
    """
    # 方法1：AutoCAD COM自动化
    dxf = _try_autocad_com(dwg_path)
    if dxf:
        return dxf, None

    # 方法2：ODA FileConverter
    converter = DWG_CONVERTER_PATH
    if os.path.exists(converter):
        dxf = _try_oda_converter(dwg_path, converter)
        if dxf:
            return dxf, None

    # 尝试常见的ODA安装路径
    oda_paths = [
        r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
        r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
        r"D:\ODA\ODAFileConverter\ODAFileConverter.exe",
    ]
    for p in oda_paths:
        if os.path.exists(p):
            dxf = _try_oda_converter(dwg_path, p)
            if dxf:
                return dxf, None

    # 方法3：LibreDWG
    dwg2dxf = shutil.which("dwg2dxf")
    if dwg2dxf:
        dxf = _try_libredwg(dwg_path, dwg2dxf)
        if dxf:
            return dxf, None

    return None, None


def _try_autocad_com(dwg_path):
    """通过AutoCAD COM自动化转换DWG→DXF"""
    if sys.platform != "win32":
        return None

    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            acad = win32com.client.Dispatch("AutoCAD.Application")
            # 如果AutoCAD未运行，尝试启动
            try:
                acad.Visible = False  # 后台运行
            except Exception:
                pass

            doc = acad.Documents.Open(os.path.abspath(dwg_path))
            output_dir = tempfile.mkdtemp(prefix="dwg2dxf_")
            dxf_name = os.path.splitext(os.path.basename(dwg_path))[0] + ".dxf"
            dxf_path = os.path.join(output_dir, dxf_name)

            # 另存为 DXF 2018 格式
            doc.SaveAs(dxf_path, 25)  # 25 = ac2018_dxf
            doc.Close()
            return dxf_path
        finally:
            pythoncom.CoUninitialize()
    except ImportError:
        # win32com 未安装，跳过
        return None
    except Exception:
        return None


def _try_oda_converter(dwg_path, converter_path):
    """通过ODA FileConverter转换"""
    output_dir = tempfile.mkdtemp(prefix="dwg2dxf_")
    input_dir = os.path.dirname(os.path.abspath(dwg_path))
    dwg_name = os.path.basename(dwg_path)

    try:
        cmd = [
            converter_path,
            input_dir,
            output_dir,
            "ACAD2018", "DXF", "0", "1",
            dwg_name,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode != 0:
            return None

        # 查找生成的DXF
        for f in os.listdir(output_dir):
            if f.lower().endswith(".dxf"):
                return os.path.join(output_dir, f)
        return None
    except Exception:
        return None


def _try_libredwg(dwg_path, converter_path):
    """通过LibreDWG转换"""
    output_dir = tempfile.mkdtemp(prefix="dwg2dxf_")
    dxf_name = os.path.splitext(os.path.basename(dwg_path))[0] + ".dxf"
    dxf_output = os.path.join(output_dir, dxf_name)

    try:
        result = subprocess.run(
            [converter_path, dwg_path, "-o", dxf_output],
            capture_output=True, text=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0 and os.path.exists(dxf_output):
            return dxf_output
        return None
    except Exception:
        return None


def _parse_dxf_annotations(file_path, warnings):
    """解析DXF文件中的文本标注 - 提取所有可能的文本实体"""
    try:
        import ezdxf
    except ImportError:
        raise ImportError("请安装 ezdxf: pip install ezdxf")

    annotations = []
    seen_texts = set()  # 去重

    # 尝试读取
    try:
        doc = ezdxf.readfile(file_path)
    except ezdxf.DXFStructureError as e:
        raise ValueError(f"DXF文件结构损坏: {str(e)}")
    except IOError:
        try:
            doc = ezdxf.readfile(file_path, encoding="gb18030")
            warnings.append("使用GB18030编码读取")
        except Exception:
            raise ValueError(f"无法读取DXF文件，文件可能已损坏")

    def add_annotation(text, x, y, z, etype, layer, handle):
        """添加标注，自动去重"""
        text = text.strip() if text else ""
        if not text:
            return
        key = f"{text}|{x:.1f}|{y:.1f}"
        if key in seen_texts:
            return
        seen_texts.add(key)
        annotations.append({
            "text_content": text,
            "cad_x": float(x),
            "cad_y": float(y),
            "cad_z": float(z) if z else 0,
            "entity_type": etype,
            "layer_name": str(layer) if layer else "",
            "entity_handle": str(handle) if handle else "",
        })

    # 遍历模型空间和所有布局
    all_spaces = [doc.modelspace()]
    try:
        for layout in doc.layouts:
            if layout.name != "Model":
                all_spaces.append(layout)
    except Exception:
        pass

    for space in all_spaces:
        # 1. TEXT
        for entity in space.query("TEXT"):
            try:
                add_annotation(entity.dxf.text,
                               entity.dxf.insert.x, entity.dxf.insert.y,
                               entity.dxf.insert.z if hasattr(entity.dxf.insert, 'z') else 0,
                               "TEXT", entity.dxf.layer, entity.dxf.handle)
            except Exception:
                pass

        # 2. MTEXT
        for entity in space.query("MTEXT"):
            try:
                text = entity.plain_text() if hasattr(entity, 'plain_text') else str(entity.text or "")
                text = re.sub(r'\\[A-Za-z][^;]*;', '', text)
                text = re.sub(r'[{}\\]', '', text).strip()
                add_annotation(text,
                               entity.dxf.insert.x, entity.dxf.insert.y,
                               entity.dxf.insert.z if hasattr(entity.dxf.insert, 'z') else 0,
                               "MTEXT", entity.dxf.layer, entity.dxf.handle)
            except Exception:
                pass

        # 3. INSERT 块属性
        for entity in space.query("INSERT"):
            try:
                for attrib in getattr(entity, 'attribs', []):
                    try:
                        add_annotation(attrib.dxf.text,
                                       entity.dxf.insert.x, entity.dxf.insert.y,
                                       entity.dxf.insert.z if hasattr(entity.dxf.insert, 'z') else 0,
                                       "ATTRIB", entity.dxf.layer, attrib.dxf.handle)
                    except Exception:
                        pass
            except Exception:
                pass

        # 4. ATTDEF 属性定义
        for entity in space.query("ATTDEF"):
            try:
                text = entity.dxf.text if hasattr(entity.dxf, 'text') else ""
                add_annotation(text,
                               entity.dxf.insert.x, entity.dxf.insert.y,
                               entity.dxf.insert.z if hasattr(entity.dxf.insert, 'z') else 0,
                               "ATTDEF", entity.dxf.layer, entity.dxf.handle)
            except Exception:
                pass

        # 5. DIMENSION 标注
        for entity in space.query("DIMENSION"):
            try:
                # 优先取用户覆盖文本，否则跳过自动生成的测量值
                if hasattr(entity.dxf, 'text') and entity.dxf.text and entity.dxf.text.strip() != "":
                    text = entity.dxf.text.strip()
                    # 跳过纯测量值（只含数字和<>）
                    if text not in ("", "<>") and not re.match(r'^[\d.]+$', text):
                        add_annotation(text,
                                       entity.dxf.text_midpoint.x if hasattr(entity.dxf, 'text_midpoint') else entity.dxf.defpoint.x,
                                       entity.dxf.text_midpoint.y if hasattr(entity.dxf, 'text_midpoint') else entity.dxf.defpoint.y,
                                       0, "DIMENSION", entity.dxf.layer, entity.dxf.handle)
            except Exception:
                pass

        # 6. MULTILEADER
        for entity in space.query("MULTILEADER"):
            try:
                if hasattr(entity, 'context') and entity.context:
                    ctx = entity.context
                    if hasattr(ctx, 'content') and ctx.content:
                        text = str(ctx.content)
                        text = re.sub(r'\\[A-Za-z][^;]*;', '', text)
                        text = re.sub(r'[{}\\]', '', text).strip()
                        add_annotation(text,
                                       entity.dxf.leader_line_end.x if hasattr(entity.dxf, 'leader_line_end') else 0,
                                       entity.dxf.leader_line_end.y if hasattr(entity.dxf, 'leader_line_end') else 0,
                                       0, "MULTILEADER", entity.dxf.layer, entity.dxf.handle)
            except Exception:
                pass

        # 7. 遍历所有实体，兜底提取未知类型中的文本
        for entity in space:
            try:
                etype = entity.dxftype()
                if etype in ("LINE", "POINT", "ARC", "CIRCLE", "LWPOLYLINE",
                             "POLYLINE", "SPLINE", "ELLIPSE", "HATCH", "SOLID",
                             "IMAGE", "XLINE", "RAY", "VIEWPORT", "OLE2FRAME"):
                    continue
                # 尝试通用方法
                for attr_name in ("text", "plain_text", "value", "label"):
                    if hasattr(entity, attr_name):
                        val = getattr(entity, attr_name)
                        if callable(val):
                            val = val()
                        if val and isinstance(val, str) and val.strip():
                            x = entity.dxf.insert.x if hasattr(entity.dxf, 'insert') else 0
                            y = entity.dxf.insert.y if hasattr(entity.dxf, 'insert') else 0
                            add_annotation(str(val).strip(), x, y, 0,
                                           etype, entity.dxf.layer if hasattr(entity.dxf, 'layer') else "",
                                           entity.dxf.handle if hasattr(entity.dxf, 'handle') else "")
            except Exception:
                pass

    if not annotations:
        warnings.append("未找到任何文本。请检查：CAD中是否有文字/标注/块属性、是否在模型空间")

    return annotations


def _match_labels(annotations):
    """提取编号 + 拆分备注"""
    if not annotations:
        return annotations

    combined_pattern = "|".join(
        f"({p})" for p in ANNOTATION_REGEX_PATTERNS
    )
    regex = re.compile(combined_pattern, re.IGNORECASE)

    for ann in annotations:
        text = ann["text_content"]
        # 尝试拆分：编号 / 备注  或  编号 备注（空格分隔）
        remark = ""
        label_text = text

        # 按 / 或 ／ 拆分
        if " / " in text:
            parts = text.split(" / ", 1)
            label_text = parts[0].strip()
            remark = parts[1].strip()
        elif "／" in text:
            parts = text.split("／", 1)
            label_text = parts[0].strip()
            remark = parts[1].strip()

        # 正则匹配编号
        match = regex.search(label_text)
        if match:
            ann["matched_label"] = match.group(0)
        else:
            ann["matched_label"] = label_text[:50]

        # 如果正则没匹配到全名，使用拆分后的前缀
        if not match or match.group(0) != label_text:
            ann["matched_label"] = label_text[:50]

        # 存储备注，后续创建调查点时自动填入
        ann["remark"] = remark

    return annotations


def get_supported_formats():
    """返回支持的CAD格式列表"""
    return list(ALLOWED_CAD_EXTENSIONS)
