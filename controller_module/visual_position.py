"""
墙与地面交界线检测算法
检测图像中墙面和地面之间的棕色瓷砖边界线
"""

import cv2
import numpy as np
import sys
from pathlib import Path


def analyze_color_at_region(image_path: str, y_start: int = None, y_end: int = None):
    """
    分析图像特定区域的颜色分布，帮助确定正确的颜色阈值
    """
    image = cv2.imread(image_path)
    if image is None:
        return
    
    height, width = image.shape[:2]
    
    if y_start is None:
        y_start = height // 3
    if y_end is None:
        y_end = height * 2 // 3
    
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    region = hsv[y_start:y_end, :, :]
    
    print(f"分析区域 y=[{y_start}, {y_end}] 的HSV颜色分布:")
    print(f"  H (色相): min={region[:,:,0].min()}, max={region[:,:,0].max()}, mean={region[:,:,0].mean():.1f}")
    print(f"  S (饱和度): min={region[:,:,1].min()}, max={region[:,:,1].max()}, mean={region[:,:,1].mean():.1f}")
    print(f"  V (明度): min={region[:,:,2].min()}, max={region[:,:,2].max()}, mean={region[:,:,2].mean():.1f}")


def detect_brown_tile_boundary(image_path: str, debug: bool = True):
    """
    检测墙与地面交界处的棕色瓷砖边界线
    
    Args:
        image_path: 图像文件路径
        debug: 是否显示调试图像
        
    Returns:
        boundary_lines: 检测到的边界线列表 [(x1, y1, x2, y2), ...]
    """
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return []
    
    original = image.copy()
    height, width = image.shape[:2]
    
    # 转换到HSV颜色空间，用于检测棕色
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 扩大棕色/木色的HSV范围以覆盖更多变化
    # 棕色/橙棕色范围
    lower_brown1 = np.array([5, 20, 40])
    upper_brown1 = np.array([30, 255, 220])
    
    # 红棕色/深棕色范围  
    lower_brown2 = np.array([0, 15, 30])
    upper_brown2 = np.array([15, 200, 180])
    
    # 偏黄的棕色
    lower_brown3 = np.array([15, 30, 60])
    upper_brown3 = np.array([35, 200, 200])
    
    # 创建棕色掩码
    mask1 = cv2.inRange(hsv, lower_brown1, upper_brown1)
    mask2 = cv2.inRange(hsv, lower_brown2, upper_brown2)
    mask3 = cv2.inRange(hsv, lower_brown3, upper_brown3)
    brown_mask = cv2.bitwise_or(mask1, mask2)
    brown_mask = cv2.bitwise_or(brown_mask, mask3)
    
    # 使用LAB颜色空间进行补充检测（棕色在a通道有正值）
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    # 棕色在LAB空间中a通道偏红，b通道偏黄
    lab_mask = cv2.inRange(lab, np.array([30, 128, 128]), np.array([180, 180, 180]))
    brown_mask = cv2.bitwise_or(brown_mask, lab_mask)
    
    # 形态学操作，去除噪声并连接相近区域
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
    brown_mask = cv2.morphologyEx(brown_mask, cv2.MORPH_CLOSE, kernel)
    brown_mask = cv2.morphologyEx(brown_mask, cv2.MORPH_OPEN, kernel)
    
    # 使用Canny边缘检测
    edges = cv2.Canny(brown_mask, 50, 150)
    
    # 膨胀边缘使其更容易检测
    kernel_dilate = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel_dilate, iterations=1)
    
    # 使用霍夫变换检测直线
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=100,
        minLineLength=width // 4,  # 最小线段长度为图像宽度的1/4
        maxLineGap=50  # 允许线段之间有一定间隙
    )
    
    boundary_lines = []
    
    if lines is not None:
        # 过滤接近水平的线（墙地交界线通常是水平的）
        horizontal_lines = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # 计算线段角度
            if x2 - x1 != 0:
                angle = np.abs(np.arctan((y2 - y1) / (x2 - x1)) * 180 / np.pi)
            else:
                angle = 90
            
            # 只保留接近水平的线（角度小于15度）
            if angle < 15:
                horizontal_lines.append((x1, y1, x2, y2))
        
        # 按y坐标分组，合并相近的线
        if horizontal_lines:
            horizontal_lines.sort(key=lambda l: (l[1] + l[3]) / 2)
            
            # 分组相近的线
            groups = []
            current_group = [horizontal_lines[0]]
            
            for line in horizontal_lines[1:]:
                current_y = (line[1] + line[3]) / 2
                group_y = sum((l[1] + l[3]) / 2 for l in current_group) / len(current_group)
                
                if abs(current_y - group_y) < 30:  # 如果y坐标相差小于30像素，归为一组
                    current_group.append(line)
                else:
                    groups.append(current_group)
                    current_group = [line]
            groups.append(current_group)
            
            # 对每个组，计算平均线
            for group in groups:
                if len(group) > 0:
                    avg_y = int(sum((l[1] + l[3]) / 2 for l in group) / len(group))
                    min_x = min(l[0] for l in group)
                    max_x = max(l[2] for l in group)
                    boundary_lines.append((min_x, avg_y, max_x, avg_y))
    
    # 方法2：使用轮廓检测作为补充
    contours, _ = cv2.findContours(brown_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        # 计算轮廓的边界框
        x, y, w, h = cv2.boundingRect(contour)
        
        # 筛选细长的水平条状物（可能是踢脚线/边界瓷砖）
        aspect_ratio = w / h if h > 0 else 0
        
        if aspect_ratio > 8 and w > width // 3:  # 宽高比大于8，且宽度大于图像宽度的1/3
            # 这可能是边界线区域
            center_y = y + h // 2
            
            # 检查是否与已检测到的线重合
            is_duplicate = False
            for bx1, by1, bx2, by2 in boundary_lines:
                if abs(center_y - by1) < 40:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                boundary_lines.append((x, center_y, x + w, center_y))
    
    # 可视化结果
    if debug:
        # 创建结果图像
        result = original.copy()
        
        # 绘制检测到的边界线
        for i, (x1, y1, x2, y2) in enumerate(boundary_lines):
            cv2.line(result, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(result, f"Line {i+1}: y={y1}", (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # 显示各阶段图像
        display_images = [
            ("Original", original),
            ("Brown Mask", cv2.cvtColor(brown_mask, cv2.COLOR_GRAY2BGR)),
            ("Edges", cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)),
            ("Result", result)
        ]
        
        # 调整图像大小以便显示
        scale = 0.5
        for name, img in display_images:
            resized = cv2.resize(img, None, fx=scale, fy=scale)
            cv2.imshow(name, resized)
        
        print(f"\n检测到 {len(boundary_lines)} 条边界线:")
        for i, (x1, y1, x2, y2) in enumerate(boundary_lines):
            print(f"  线 {i+1}: 从 ({x1}, {y1}) 到 ({x2}, {y2}), y位置 = {y1}")
        
        print("\n按任意键关闭窗口...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        # 保存结果图像
        output_path = str(Path(image_path).stem) + "_boundary_result.jpg"
        cv2.imwrite(output_path, result)
        print(f"结果已保存到: {output_path}")
    
    return boundary_lines


def detect_boundary_by_gradient(image_path: str, debug: bool = True):
    """
    使用梯度变化检测墙地交界线
    这种方法适用于交界处有明显颜色/亮度变化的情况
    
    Args:
        image_path: 图像文件路径
        debug: 是否显示调试图像
        
    Returns:
        boundary_y: 检测到的边界线y坐标
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return None
    
    original = image.copy()
    height, width = image.shape[:2]
    
    # 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 高斯模糊减少噪声
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # 计算垂直方向的Sobel梯度（检测水平边缘）
    sobel_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=5)
    sobel_y = np.abs(sobel_y)
    
    # 计算每行的平均梯度强度
    row_gradients = np.mean(sobel_y, axis=1)
    
    # 找到梯度最强的位置（可能是边界线）
    # 只在图像中间1/3到下方2/3区域搜索（墙地交界线通常在这个范围）
    search_start = height // 3
    search_end = height * 2 // 3
    
    search_region = row_gradients[search_start:search_end]
    
    # 找到峰值
    max_gradient_idx = np.argmax(search_region) + search_start
    
    if debug:
        result = original.copy()
        
        # 绘制检测到的边界线
        cv2.line(result, (0, max_gradient_idx), (width, max_gradient_idx), (0, 0, 255), 3)
        cv2.putText(result, f"Gradient Boundary: y={max_gradient_idx}", 
                   (10, max_gradient_idx - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # 绘制梯度分布图
        gradient_vis = np.zeros((height, 200, 3), dtype=np.uint8)
        normalized = (row_gradients / row_gradients.max() * 180).astype(np.int32)
        for y in range(height):
            cv2.line(gradient_vis, (0, y), (normalized[y], y), (255, 255, 255), 1)
        cv2.line(gradient_vis, (0, max_gradient_idx), (200, max_gradient_idx), (0, 0, 255), 2)
        
        # 显示结果
        scale = 0.5
        cv2.imshow("Gradient Result", cv2.resize(result, None, fx=scale, fy=scale))
        cv2.imshow("Row Gradients", cv2.resize(gradient_vis, None, fx=scale, fy=scale))
        
        print(f"\n梯度方法检测到边界线 y = {max_gradient_idx}")
        
    return max_gradient_idx


def detect_floor_wall_boundary(image_path: str, debug: bool = True):
    """
    综合多种方法检测墙地交界线
    
    Args:
        image_path: 图像文件路径
        debug: 是否显示调试图像
        
    Returns:
        dict: 包含检测结果的字典
    """
    print("=" * 50)
    print("墙地交界线检测")
    print("=" * 50)
    
    # 方法1：棕色瓷砖检测
    print("\n[方法1] 棕色瓷砖边界检测...")
    brown_lines = detect_brown_tile_boundary(image_path, debug=False)
    
    # 方法2：梯度检测
    print("\n[方法2] 梯度边界检测...")
    gradient_y = detect_boundary_by_gradient(image_path, debug=False)
    
    # 读取原图用于综合可视化
    image = cv2.imread(image_path)
    if image is None:
        return {"brown_lines": brown_lines, "gradient_y": gradient_y}
    
    result = image.copy()
    height, width = image.shape[:2]
    
    # 绘制棕色瓷砖检测结果（绿色）
    for i, (x1, y1, x2, y2) in enumerate(brown_lines):
        cv2.line(result, (x1, y1), (x2, y2), (0, 255, 0), 3)
    
    # 绘制梯度检测结果（红色）
    if gradient_y is not None:
        cv2.line(result, (0, gradient_y), (width, gradient_y), (0, 0, 255), 2)
    
    # 添加图例
    cv2.putText(result, "Green: Brown Tile Detection", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(result, "Red: Gradient Detection", (10, 60),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    if debug:
        # 显示综合结果
        scale = 0.5
        cv2.imshow("Combined Result", cv2.resize(result, None, fx=scale, fy=scale))
        
        print("\n" + "=" * 50)
        print("检测结果汇总:")
        print("=" * 50)
        print(f"棕色瓷砖检测: 找到 {len(brown_lines)} 条边界线")
        for i, (x1, y1, x2, y2) in enumerate(brown_lines):
            print(f"  - 线 {i+1}: y = {y1}")
        print(f"梯度检测: y = {gradient_y}")
        
        print("\n按任意键关闭窗口...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        # 保存结果
        output_path = str(Path(image_path).stem) + "_combined_result.jpg"
        cv2.imwrite(output_path, result)
        print(f"综合结果已保存到: {output_path}")
    
    return {
        "brown_lines": brown_lines,
        "gradient_y": gradient_y,
        "result_image": result
    }


def detect_baseboard_hsv(image_path: str, debug: bool = True):
    """
    使用HSV颜色空间专门检测踢脚线/边界瓷砖
    针对棕色/木色踢脚线优化
    
    Args:
        image_path: 图像文件路径
        debug: 是否显示调试图像
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return []
    
    original = image.copy()
    height, width = image.shape[:2]
    
    # 转换到不同颜色空间
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    
    # 定义多个棕色/木色范围
    brown_ranges = [
        # 浅棕色
        (np.array([8, 40, 80]), np.array([25, 200, 220])),
        # 深棕色
        (np.array([5, 30, 40]), np.array([20, 180, 160])),
        # 红棕色
        (np.array([0, 50, 50]), np.array([15, 200, 200])),
    ]
    
    combined_mask = np.zeros((height, width), dtype=np.uint8)
    
    for lower, upper in brown_ranges:
        mask = cv2.inRange(hsv, lower, upper)
        combined_mask = cv2.bitwise_or(combined_mask, mask)
    
    # 形态学处理 - 保持水平结构
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 3))
    processed_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel_h)
    processed_mask = cv2.morphologyEx(processed_mask, cv2.MORPH_OPEN, kernel_h)
    
    # 寻找水平方向上的连续区域
    # 计算每行的非零像素数
    row_counts = np.sum(processed_mask > 0, axis=1)
    
    # 找到像素数较多的行（可能是踢脚线区域）
    threshold = width * 0.3  # 至少覆盖30%宽度
    candidate_rows = np.where(row_counts > threshold)[0]
    
    boundary_lines = []
    
    if len(candidate_rows) > 0:
        # 分组连续的行
        groups = []
        current_group = [candidate_rows[0]]
        
        for row in candidate_rows[1:]:
            if row - current_group[-1] <= 5:  # 允许5像素间隙
                current_group.append(row)
            else:
                if len(current_group) >= 3:  # 至少3行连续
                    groups.append(current_group)
                current_group = [row]
        
        if len(current_group) >= 3:
            groups.append(current_group)
        
        # 对每个组计算边界线
        for group in groups:
            y_top = min(group)
            y_bottom = max(group)
            y_center = (y_top + y_bottom) // 2
            
            # 找到这些行中非零像素的x范围
            mask_region = processed_mask[y_top:y_bottom+1, :]
            x_coords = np.where(np.any(mask_region > 0, axis=0))[0]
            
            if len(x_coords) > 0:
                x_min = x_coords[0]
                x_max = x_coords[-1]
                
                # 上边界线
                boundary_lines.append({
                    "type": "top",
                    "line": (x_min, y_top, x_max, y_top),
                    "y": y_top
                })
                # 下边界线
                boundary_lines.append({
                    "type": "bottom", 
                    "line": (x_min, y_bottom, x_max, y_bottom),
                    "y": y_bottom
                })
    
    if debug:
        result = original.copy()
        
        # 绘制检测到的边界线
        colors = {"top": (0, 255, 255), "bottom": (255, 0, 255)}  # 黄色和品红
        
        for boundary in boundary_lines:
            x1, y1, x2, y2 = boundary["line"]
            color = colors[boundary["type"]]
            cv2.line(result, (x1, y1), (x2, y2), color, 2)
            label = f"{boundary['type']}: y={boundary['y']}"
            cv2.putText(result, label, (x1, y1 - 5 if boundary["type"] == "top" else y1 + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # 显示结果
        scale = 0.5
        cv2.imshow("Original", cv2.resize(original, None, fx=scale, fy=scale))
        cv2.imshow("Brown Mask", cv2.resize(combined_mask, None, fx=scale, fy=scale))
        cv2.imshow("Processed Mask", cv2.resize(processed_mask, None, fx=scale, fy=scale))
        cv2.imshow("Baseboard Detection", cv2.resize(result, None, fx=scale, fy=scale))
        
        print(f"\n检测到 {len(boundary_lines)} 条边界线:")
        for b in boundary_lines:
            print(f"  {b['type']}: y = {b['y']}")
        
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        # 保存结果
        output_path = str(Path(image_path).stem) + "_baseboard_result.jpg"
        cv2.imwrite(output_path, result)
        print(f"结果已保存到: {output_path}")
    
    return boundary_lines


def detect_corridor_boundary(image_path: str, debug: bool = True):
    """
    专门针对走廊场景的墙地交界线检测
    结合边缘检测、颜色分析和透视特征
    
    Args:
        image_path: 图像文件路径
        debug: 是否显示调试图像
        
    Returns:
        list: 检测到的边界线信息
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return []
    
    original = image.copy()
    height, width = image.shape[:2]
    
    # 1. 边缘检测
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    
    # 2. 颜色分析 - 检测棕色/木色区域
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 扩展的棕色范围
    brown_masks = []
    brown_ranges = [
        (np.array([0, 20, 30]), np.array([25, 200, 200])),    # 红棕色
        (np.array([10, 30, 50]), np.array([30, 200, 220])),   # 橙棕色
        (np.array([5, 15, 40]), np.array([20, 150, 180])),    # 深棕色
    ]
    
    combined_brown = np.zeros((height, width), dtype=np.uint8)
    for lower, upper in brown_ranges:
        mask = cv2.inRange(hsv, lower, upper)
        combined_brown = cv2.bitwise_or(combined_brown, mask)
    
    # 3. 结合边缘和颜色信息
    # 膨胀棕色区域以找到边界
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 5))
    dilated_brown = cv2.dilate(combined_brown, kernel, iterations=2)
    
    # 找到棕色区域的边缘
    brown_edges = cv2.Canny(dilated_brown, 50, 150)
    
    # 4. 使用霍夫变换检测水平线
    all_lines = []
    
    # 从边缘图检测
    lines1 = cv2.HoughLinesP(edges, 1, np.pi/180, 80, minLineLength=width//5, maxLineGap=30)
    if lines1 is not None:
        all_lines.extend(lines1)
    
    # 从棕色边缘检测
    lines2 = cv2.HoughLinesP(brown_edges, 1, np.pi/180, 50, minLineLength=width//6, maxLineGap=40)
    if lines2 is not None:
        all_lines.extend(lines2)
    
    # 5. 过滤和分析线段
    horizontal_lines = []
    for line in all_lines:
        x1, y1, x2, y2 = line[0]
        
        # 计算角度
        dx = x2 - x1
        dy = y2 - y1
        if dx != 0:
            angle = np.abs(np.arctan(dy / dx) * 180 / np.pi)
        else:
            angle = 90
        
        # 只保留接近水平的线（<10度）
        if angle < 10:
            length = np.sqrt(dx*dx + dy*dy)
            y_avg = (y1 + y2) / 2
            horizontal_lines.append({
                'line': (x1, y1, x2, y2),
                'y': y_avg,
                'length': length,
                'x_range': (min(x1, x2), max(x1, x2))
            })
    
    # 6. 按y坐标聚类
    if horizontal_lines:
        horizontal_lines.sort(key=lambda x: x['y'])
        
        clusters = []
        current_cluster = [horizontal_lines[0]]
        
        for line in horizontal_lines[1:]:
            cluster_y = np.mean([l['y'] for l in current_cluster])
            if abs(line['y'] - cluster_y) < 25:  # 25像素阈值
                current_cluster.append(line)
            else:
                clusters.append(current_cluster)
                current_cluster = [line]
        clusters.append(current_cluster)
        
        # 7. 分析每个聚类，找出最可能的边界线
        boundary_candidates = []
        for cluster in clusters:
            total_length = sum(l['length'] for l in cluster)
            avg_y = np.mean([l['y'] for l in cluster])
            x_min = min(l['x_range'][0] for l in cluster)
            x_max = max(l['x_range'][1] for l in cluster)
            
            # 检查该y位置附近是否有颜色变化（从白色/浅色到棕色）
            y_int = int(avg_y)
            if 10 < y_int < height - 10:
                region_above = hsv[max(0, y_int-20):y_int, :, :]
                region_below = hsv[y_int:min(height, y_int+20), :, :]
                
                # 计算颜色差异
                above_hue = np.mean(region_above[:,:,0])
                below_hue = np.mean(region_below[:,:,0])
                above_sat = np.mean(region_above[:,:,1])
                below_sat = np.mean(region_below[:,:,1])
                
                color_diff = abs(above_hue - below_hue) + abs(above_sat - below_sat) / 5
            else:
                color_diff = 0
            
            boundary_candidates.append({
                'y': avg_y,
                'x_range': (x_min, x_max),
                'total_length': total_length,
                'line_count': len(cluster),
                'color_diff': color_diff,
                'score': total_length * 0.3 + color_diff * 10 + len(cluster) * 20
            })
        
        # 按分数排序
        boundary_candidates.sort(key=lambda x: x['score'], reverse=True)
    else:
        boundary_candidates = []
    
    # 8. 可视化结果
    if debug:
        result = original.copy()
        
        # 绘制所有检测到的水平线（灰色，细线）
        for line in horizontal_lines:
            x1, y1, x2, y2 = line['line']
            cv2.line(result, (int(x1), int(y1)), (int(x2), int(y2)), (128, 128, 128), 1)
        
        # 绘制最佳边界候选（按分数着色）
        colors = [(0, 255, 0), (0, 255, 255), (0, 165, 255), (0, 0, 255)]
        for i, candidate in enumerate(boundary_candidates[:4]):
            y = int(candidate['y'])
            x1, x2 = int(candidate['x_range'][0]), int(candidate['x_range'][1])
            color = colors[min(i, len(colors)-1)]
            thickness = 4 - i if i < 3 else 1
            cv2.line(result, (x1, y), (x2, y), color, thickness)
            
            label = f"#{i+1} y={y} score={candidate['score']:.0f}"
            cv2.putText(result, label, (x1, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # 创建调试视图
        debug_view = np.zeros((height, width, 3), dtype=np.uint8)
        debug_view[:,:,0] = combined_brown  # 蓝色通道显示棕色掩码
        debug_view[:,:,1] = edges  # 绿色通道显示边缘
        debug_view[:,:,2] = brown_edges  # 红色通道显示棕色边缘
        
        scale = 0.5
        cv2.imshow("Original", cv2.resize(original, None, fx=scale, fy=scale))
        cv2.imshow("Edges", cv2.resize(edges, None, fx=scale, fy=scale))
        cv2.imshow("Brown Mask", cv2.resize(combined_brown, None, fx=scale, fy=scale))
        cv2.imshow("Debug View (B=brown, G=edges, R=brown_edges)", cv2.resize(debug_view, None, fx=scale, fy=scale))
        cv2.imshow("Corridor Boundary Detection", cv2.resize(result, None, fx=scale, fy=scale))
        
        print("\n走廊边界检测结果:")
        print(f"检测到 {len(horizontal_lines)} 条水平线段")
        print(f"聚类后得到 {len(boundary_candidates)} 个边界候选")
        
        if boundary_candidates:
            print("\n最佳边界候选 (按分数排序):")
            for i, c in enumerate(boundary_candidates[:5]):
                print(f"  #{i+1}: y={c['y']:.0f}, 长度={c['total_length']:.0f}, "
                      f"线段数={c['line_count']}, 颜色差异={c['color_diff']:.1f}, 分数={c['score']:.0f}")
        
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        output_path = str(Path(image_path).stem) + "_corridor_result.jpg"
        cv2.imwrite(output_path, result)
        print(f"\n结果已保存到: {output_path}")
    
    return boundary_candidates


def detect_perspective_boundary(image_path: str, debug: bool = True):
    """
    检测走廊透视视角下的墙地交界线（踢脚线）
    专门检测走廊两侧墙壁底部的斜向踢脚线，排除门框和天花板
    
    Args:
        image_path: 图像文件路径
        debug: 是否显示调试图像
        
    Returns:
        dict: 包含左右两侧边界线的检测结果
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return {}
    
    original = image.copy()
    height, width = image.shape[:2]
    center_x = width // 2
    center_y = height // 2
    
    # 1. 转换颜色空间
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 2. 边缘检测 - 主要方法
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    
    # 3. 棕色区域检测 - 扩大范围覆盖更多棕色变体
    brown_ranges = [
        (np.array([0, 30, 30]), np.array([25, 255, 220])),    # 宽泛的棕色
        (np.array([5, 20, 40]), np.array([20, 200, 200])),    # 浅棕色
        (np.array([0, 40, 50]), np.array([15, 255, 180])),    # 红棕色
        (np.array([10, 30, 60]), np.array([25, 180, 200])),   # 橙棕色
    ]
    
    brown_mask = np.zeros((height, width), dtype=np.uint8)
    for lower, upper in brown_ranges:
        mask = cv2.inRange(hsv, lower, upper)
        brown_mask = cv2.bitwise_or(brown_mask, mask)
    
    # 4. 创建左右两侧的感兴趣区域（ROI）
    # 左侧踢脚线区域：靠近左边墙壁，扩大范围
    left_roi = np.zeros((height, width), dtype=np.uint8)
    left_pts = np.array([
        [0, height - 1],                      # 左下角
        [0, int(height * 0.15)],              # 左边上部（更高）
        [int(width * 0.55), int(height * 0.15)],  # 中上偏左（更宽）
        [int(width * 0.45), height - 1]       # 中下偏左（更宽）
    ], np.int32)
    cv2.fillPoly(left_roi, [left_pts], 255)
    
    # 右侧踢脚线区域：靠近右边墙壁，扩大范围
    right_roi = np.zeros((height, width), dtype=np.uint8)
    right_pts = np.array([
        [width - 1, height - 1],              # 右下角
        [width - 1, int(height * 0.15)],      # 右边上部（更高）
        [int(width * 0.45), int(height * 0.15)],  # 中上偏右（更宽）
        [int(width * 0.55), height - 1]       # 中下偏右（更宽）
    ], np.int32)
    cv2.fillPoly(right_roi, [right_pts], 255)
    
    # 5. 在ROI内检测边缘
    left_edges = cv2.bitwise_and(edges, left_roi)
    right_edges = cv2.bitwise_and(edges, right_roi)
    
    # 6. 使用霍夫变换检测直线
    left_lines_raw = cv2.HoughLinesP(left_edges, 1, np.pi/180, 40, 
                                      minLineLength=80, maxLineGap=40)
    right_lines_raw = cv2.HoughLinesP(right_edges, 1, np.pi/180, 40, 
                                       minLineLength=80, maxLineGap=40)
    
    # 7. 验证线段是否在棕色区域边缘（踢脚线特征）
    def is_near_brown_region(line, brown_mask, hsv, threshold=0.3):
        """
        检查线段是否位于棕色区域的边缘
        踢脚线的一侧应该是棕色，另一侧是浅色（墙面或地面）
        """
        x1, y1, x2, y2 = line
        
        # 采样线段上的多个点
        num_samples = 10
        brown_count = 0
        
        for i in range(num_samples):
            t = i / (num_samples - 1)
            px = int(x1 + t * (x2 - x1))
            py = int(y1 + t * (y2 - y1))
            
            # 确保坐标在图像范围内
            px = max(0, min(px, brown_mask.shape[1] - 1))
            py = max(0, min(py, brown_mask.shape[0] - 1))
            
            # 检查该点周围是否有棕色像素（踢脚线）
            # 检查线段两侧
            offset = 10
            
            # 计算垂直于线段的方向
            dx = x2 - x1
            dy = y2 - y1
            length = np.sqrt(dx*dx + dy*dy)
            if length == 0:
                continue
            
            # 垂直方向（法向量）
            nx = -dy / length
            ny = dx / length
            
            # 检查线段两侧的像素
            side1_x = int(px + nx * offset)
            side1_y = int(py + ny * offset)
            side2_x = int(px - nx * offset)
            side2_y = int(py - ny * offset)
            
            # 边界检查
            h, w = brown_mask.shape[:2]
            side1_x = max(0, min(side1_x, w - 1))
            side1_y = max(0, min(side1_y, h - 1))
            side2_x = max(0, min(side2_x, w - 1))
            side2_y = max(0, min(side2_y, h - 1))
            
            # 检查是否有一侧是棕色，另一侧不是（边缘特征）
            side1_brown = brown_mask[side1_y, side1_x] > 0
            side2_brown = brown_mask[side2_y, side2_x] > 0
            
            # 如果两侧颜色不同（一侧棕色，一侧不是），则这是边缘
            if side1_brown != side2_brown:
                brown_count += 1
        
        # 如果超过阈值比例的采样点位于棕色边缘，则认为是踢脚线
        return brown_count / num_samples >= threshold
    
    # 8. 处理检测到的线段
    def process_lines(lines_raw, side):
        if lines_raw is None:
            return [], []
        
        result = []
        all_debug = []
        for line in lines_raw:
            x1, y1, x2, y2 = line[0]
            
            # 计算基本属性
            dx = x2 - x1
            dy = y2 - y1
            length = np.sqrt(dx*dx + dy*dy)
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            
            if dx != 0:
                angle = np.arctan(dy / dx) * 180 / np.pi
            else:
                angle = 90
            
            all_debug.append({
                'line': (x1, y1, x2, y2),
                'angle': angle,
                'length': length,
                'center': (cx, cy)
            })
            
            if length < 60:
                continue
            
            # 检查是否在棕色区域边缘（降低阈值使其更宽松）
            if not is_near_brown_region((x1, y1, x2, y2), brown_mask, hsv, threshold=0.15):
                continue
            
            # 踢脚线的角度特征（基于图像坐标系，y向下为正）
            # 对于靠近边缘的线段，允许更大的角度范围（可能接近垂直）
            
            if side == 'left':
                # 左侧：检查负角度
                # 如果线段非常靠近左边缘（x < width*0.1），允许更陡的角度
                min_x = min(x1, x2)
                if min_x < width * 0.1:
                    # 靠近边缘的线：允许 -88° 到 -10°
                    valid_angle = -88 < angle < -10
                else:
                    # 远离边缘的线：只允许 -70° 到 -10°
                    valid_angle = -70 < angle < -10
                
                if valid_angle:
                    result.append({
                        'line': (x1, y1, x2, y2),
                        'angle': angle,
                        'center': (cx, cy),
                        'length': length
                    })
            else:  # right
                # 右侧：检查正角度
                max_x = max(x1, x2)
                if max_x > width * 0.9:
                    valid_angle = 10 < angle < 88
                else:
                    valid_angle = 10 < angle < 70
                    
                if valid_angle:
                    result.append({
                        'line': (x1, y1, x2, y2),
                        'angle': angle,
                        'center': (cx, cy),
                        'length': length
                    })
        
        return result, all_debug
    
    left_lines, left_debug = process_lines(left_lines_raw, 'left')
    right_lines, right_debug = process_lines(right_lines_raw, 'right')
    
    # 8. 直接从棕色掩码边界拟合踢脚线（更可靠的方法）
    def fit_baseboard_from_brown_boundary(brown_mask, side='left'):
        """
        通过分析棕色掩码的边界来拟合踢脚线
        左侧：找每行最右边的棕色像素
        右侧：找每行最左边的棕色像素
        """
        h, w = brown_mask.shape[:2]
        boundary_points = []
        
        # 只分析图像下半部分（踢脚线通常在下方）
        y_start = h // 3
        y_end = h - 20  # 留一点边距避免底部噪声
        
        for y in range(y_start, y_end, 5):
            if side == 'left':
                # 左侧踢脚线：只看左边1/4区域
                row = brown_mask[y, :w//4]
                brown_pixels = np.where(row > 0)[0]
                if len(brown_pixels) > 0:
                    # 取最右边的棕色像素作为边界
                    x = brown_pixels.max()
                    if x > 10:  # 排除紧贴边缘的噪声
                        boundary_points.append((x, y))
            else:
                # 右侧踢脚线：只看右边1/4区域
                row = brown_mask[y, 3*w//4:]
                brown_pixels = np.where(row > 0)[0]
                if len(brown_pixels) > 0:
                    # 取最左边的棕色像素作为边界
                    x = brown_pixels.min() + 3*w//4
                    if x < w - 10:
                        boundary_points.append((x, y))
        
        if len(boundary_points) < 10:
            return None
        
        pts = np.array(boundary_points)
        
        # 使用RANSAC思想：移除异常值
        # 先用中位数过滤
        x_vals = pts[:, 0]
        median_x = np.median(x_vals)
        std_x = np.std(x_vals)
        
        # 只保留在合理范围内的点
        valid_mask = np.abs(x_vals - median_x) < 2 * std_x
        pts_filtered = pts[valid_mask]
        
        if len(pts_filtered) < 5:
            return None
        
        # 线性回归拟合: x = m * y + c
        x = pts_filtered[:, 0]
        y = pts_filtered[:, 1]
        A = np.vstack([y, np.ones(len(y))]).T
        result = np.linalg.lstsq(A, x, rcond=None)
        m, c = result[0]
        
        # 计算角度
        angle = np.arctan(m) * 180 / np.pi
        
        # 计算线段端点
        y1 = y_start
        y2 = y_end
        x1 = int(m * y1 + c)
        x2 = int(m * y2 + c)
        
        # 计算长度
        length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
        
        # 验证角度是否合理（踢脚线应该是斜向的，不是垂直或水平的）
        if side == 'left' and not (-60 < angle < -5):
            return None
        if side == 'right' and not (5 < angle < 60):
            return None
        
        return {
            'line': (x1, y1, x2, y2),
            'angle': angle,
            'center': ((x1+x2)/2, (y1+y2)/2),
            'length': length,
            'source': 'brown_boundary'
        }
    
    # 9. 选择最佳的踢脚线 - 返回两条边界线（外边界和内边界）
    def select_best_line(lines_list, side='left'):
        if not lines_list:
            return None, None
        
        # 过滤掉位置不合理的线段
        # 踢脚线应该靠近图像边缘，但内边界可能更靠近中央
        filtered = []
        for line in lines_list:
            cx, cy = line['center']
            # 左侧踢脚线：中心应该在左半部分（放宽到50%以容纳内边界）
            if side == 'left' and cx < width * 0.50:
                filtered.append(line)
            # 右侧踢脚线：中心应该在右半部分（放宽到50%以容纳内边界）
            elif side == 'right' and cx > width * 0.50:
                filtered.append(line)
        
        if debug and side == 'left':
            print(f"  [调试] 左侧候选线位置过滤: 共{len(lines_list)}条, 过滤后{len(filtered)}条 (阈值: cx < {width * 0.50:.0f})")
            for i, line in enumerate(lines_list[:5]):
                cx, cy = line['center']
                print(f"    线{i}: 中心=({cx:.0f},{cy:.0f}), 角度={line['angle']:.1f}, 长度={line['length']:.0f}")
        
        if debug and side == 'right':
            print(f"  [调试] 右侧候选线位置过滤: 共{len(lines_list)}条, 过滤后{len(filtered)}条 (阈值: cx > {width * 0.50:.0f})")
            for i, line in enumerate(filtered[:5]):
                cx, cy = line['center']
                print(f"    线{i}: 中心=({cx:.0f},{cy:.0f}), 角度={line['angle']:.1f}, 长度={line['length']:.0f}")
        
        if not filtered:
            return None, None  # 返回两条边界线
        
        # 按长度排序
        sorted_lines = sorted(filtered, key=lambda x: x['length'], reverse=True)
        
        # 选择最长的线作为主边界
        primary = sorted_lines[0]
        
        # 寻找第二条边界线（踢脚线的另一侧）
        # 条件：角度相近，但位置有一定偏移
        secondary = None
        for line in sorted_lines[1:]:
            # 角度差在15度以内
            angle_diff = abs(line['angle'] - primary['angle'])
            if angle_diff > 15:
                continue
            
            # 计算垂直于线段方向的距离（而不是简单的x偏移）
            cx1, cy1 = primary['center']
            cx2, cy2 = line['center']
            
            # 线段的方向向量
            angle_rad = np.radians(primary['angle'])
            # 垂直于线段的单位向量
            nx = -np.sin(angle_rad)
            ny = np.cos(angle_rad)
            
            # 计算两个中心点在垂直方向上的距离
            dx = cx2 - cx1
            dy = cy2 - cy1
            perp_dist = abs(dx * nx + dy * ny)
            
            # 踢脚线宽度大约在 15-150 像素（根据图像分辨率调整）
            min_width = max(10, min(width, height) * 0.02)  # 最小宽度为图像短边的2%
            max_width = min(200, min(width, height) * 0.25)  # 最大宽度为图像短边的25%
            
            if min_width < perp_dist < max_width:
                # 检查两条线之间是否为棕色区域
                if not is_brown_between_lines(primary, line, brown_mask):
                    continue
                secondary = line
                break
        
        # 确保内边界（secondary）在外边界（primary）的正确位置
        if primary and secondary:
            cx1, cy1 = primary['center']
            cx2, cy2 = secondary['center']
            
            if side == 'left':
                # 左侧踢脚线：内边界应该x更大（更靠右/中心）
                if cx2 < cx1:
                    primary, secondary = secondary, primary
            else:  # right
                # 右侧踢脚线：内边界应该x更小（更靠左/中心）
                if cx2 > cx1:
                    primary, secondary = secondary, primary
        
        return primary, secondary
    
    # 检查两条线之间是否为棕色区域 - 放宽检测
    def is_brown_between_lines(line1, line2, brown_mask):
        x1a, y1a, x2a, y2a = line1['line']
        x1b, y1b, x2b, y2b = line2['line']
        
        num_samples = 5
        brown_count = 0
        total_count = 0
        
        for i in range(num_samples):
            t = (i + 1) / (num_samples + 1)
            px1 = int(x1a + t * (x2a - x1a))
            py1 = int(y1a + t * (y2a - y1a))
            px2 = int(x1b + t * (x2b - x1b))
            py2 = int(y1b + t * (y2b - y1b))
            
            # 在两点之间的中点采样
            px = int((px1 + px2) / 2)
            py = int((py1 + py2) / 2)
            
            px = max(0, min(px, brown_mask.shape[1] - 1))
            py = max(0, min(py, brown_mask.shape[0] - 1))
            
            if brown_mask[py, px] > 0:
                brown_count += 1
            total_count += 1
        
        # 只要有20%的区域是棕色就算通过
        return brown_count / total_count >= 0.2 if total_count > 0 else True
    
    # 优先使用霍夫变换检测到的候选线（更准确）
    best_left, second_left = select_best_line(left_lines, 'left')
    best_right, second_right = select_best_line(right_lines, 'right')
    
    # 如果霍夫变换没有结果，尝试使用棕色边界拟合
    if not best_left:
        best_left = fit_baseboard_from_brown_boundary(brown_mask, 'left')
    if not best_right:
        best_right = fit_baseboard_from_brown_boundary(brown_mask, 'right')
    
    # 10. 可视化
    if debug:
        result = original.copy()
        
        # 绘制区域掩码边界（调试用 - 黄色左侧，青色右侧）
        cv2.polylines(result, [left_pts], True, (0, 255, 255), 2)
        cv2.polylines(result, [right_pts], True, (255, 255, 0), 2)
        
        # 绘制所有候选线段（细线）
        for line_info in left_lines:
            x1, y1, x2, y2 = line_info['line']
            cv2.line(result, (x1, y1), (x2, y2), (100, 200, 100), 1)
        for line_info in right_lines:
            x1, y1, x2, y2 = line_info['line']
            cv2.line(result, (x1, y1), (x2, y2), (200, 100, 100), 1)
        
        # 绘制左侧踢脚线边界（绿色 - 主边界粗线，副边界中等线）
        if best_left:
            x1, y1, x2, y2 = best_left['line']
            cv2.line(result, (x1, y1), (x2, y2), (0, 255, 0), 4)
            cv2.putText(result, f"L1: {best_left['angle']:.1f}deg", 
                       (x1+5, y1+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        if second_left:
            x1, y1, x2, y2 = second_left['line']
            cv2.line(result, (x1, y1), (x2, y2), (0, 200, 0), 3)
            cv2.putText(result, f"L2: {second_left['angle']:.1f}deg", 
                       (x1+5, y1+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2)
        
        # 绘制右侧踢脚线边界（红色 - 主边界粗线，副边界中等线）
        if best_right:
            x1, y1, x2, y2 = best_right['line']
            cv2.line(result, (x1, y1), (x2, y2), (0, 0, 255), 4)
            cv2.putText(result, f"R1: {best_right['angle']:.1f}deg", 
                       (x1-80, y1+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        if second_right:
            x1, y1, x2, y2 = second_right['line']
            cv2.line(result, (x1, y1), (x2, y2), (0, 0, 200), 3)
            cv2.putText(result, f"R2: {second_right['angle']:.1f}deg", 
                       (x1-80, y1+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 200), 2)
        
        # 图例
        cv2.putText(result, "Green: Left baseboard (L1=outer, L2=inner)", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(result, "Red: Right baseboard (R1=outer, R2=inner)", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        scale = 0.5
        cv2.imshow("Original", cv2.resize(original, None, fx=scale, fy=scale))
        cv2.imshow("Left ROI Edges", cv2.resize(left_edges, None, fx=scale, fy=scale))
        cv2.imshow("Right ROI Edges", cv2.resize(right_edges, None, fx=scale, fy=scale))
        cv2.imshow("Baseboard Detection", cv2.resize(result, None, fx=scale, fy=scale))
        
        print(f"\n踢脚线检测结果:")
        print(f"  检测到左侧候选线: {len(left_lines)} 条")
        print(f"  检测到右侧候选线: {len(right_lines)} 条")
        if best_left:
            print(f"  左侧踢脚线外边界: 角度={best_left['angle']:.1f}度, 长度={best_left['length']:.0f}")
        if second_left:
            print(f"  左侧踢脚线内边界: 角度={second_left['angle']:.1f}度, 长度={second_left['length']:.0f}")
        if not best_left:
            print(f"  未检测到左侧踢脚线")
        if best_right:
            print(f"  右侧踢脚线外边界: 角度={best_right['angle']:.1f}度, 长度={best_right['length']:.0f}")
        if second_right:
            print(f"  右侧踢脚线内边界: 角度={second_right['angle']:.1f}度, 长度={second_right['length']:.0f}")
        if not best_right:
            print(f"  未检测到右侧踢脚线")
        
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        output_path = str(Path(image_path).stem) + "_baseboard_detect.jpg"
        cv2.imwrite(output_path, result)
        print(f"\n结果已保存到: {output_path}")
    
    return {
        'left': best_left,
        'left_inner': second_left,
        'right': best_right,
        'right_inner': second_right,
        'left_candidates': left_lines,
        'right_candidates': right_lines
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python visual_position.py <图像路径>")
        print("示例: python visual_position.py floor5.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    print(f"正在处理图像: {image_path}")
    print()
    
    # 只运行踢脚线检测
    print("=" * 50)
    print("走廊踢脚线检测")
    print("=" * 50)
    result = detect_perspective_boundary(image_path, debug=True)
