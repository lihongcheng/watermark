from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from PIL import Image, ImageDraw, ImageFont
import base64
import io
import uuid
from datetime import datetime
import logging
import tempfile
import requests
import math

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
CORS(app)

UPLOAD_FOLDER = 'static/uploads'
RESULT_FOLDER = 'static/results'
FONTS_FOLDER = 'static/fonts'

# 确保目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
os.makedirs(FONTS_FOLDER, exist_ok=True)

# 中文字体文件URL
FONT_URL = "https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/SourceHanSansSC-Bold.otf"
FONT_PATH = os.path.join(FONTS_FOLDER, "SourceHanSansSC-Bold.otf")

# 确保字体文件存在
def ensure_font_exists():
    if not os.path.exists(FONT_PATH):
        try:
            logger.info("下载中文字体文件...")
            r = requests.get(FONT_URL, stream=True)
            if r.status_code == 200:
                with open(FONT_PATH, 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                logger.info(f"字体文件已下载到 {FONT_PATH}")
            else:
                logger.error(f"字体下载失败，状态码: {r.status_code}")
        except Exception as e:
            logger.error(f"字体下载过程中出错: {str(e)}")

# 尝试加载中文字体
ensure_font_exists()

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/watermark', methods=['POST'])
def add_watermark():
    data = request.json
    
    # 解析base64图片
    try:
        image_data = data['image'].split(',')[1]
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        logger.debug(f"成功加载图片，尺寸: {image.size}, 模式: {image.mode}")
    except Exception as e:
        logger.error(f"图片加载失败: {str(e)}")
        return jsonify({'success': False, 'error': '图片加载失败'})
    
    # 水印参数
    text = data['text']
    opacity = float(data['opacity']) / 100
    color = data['color']
    angle = int(data['angle'])
    # 添加字体大小参数
    font_size_percent = int(data.get('fontSize', 10))  # 默认为图片较短边的10%
    
    logger.debug(f"水印参数: 文字='{text}', 不透明度={opacity}, 颜色={color}, 角度={angle}, 字体大小百分比={font_size_percent}")
    
    # 转换颜色格式 (#RRGGBB -> RGB)
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    
    # 创建一个新的RGBA图层，完全透明
    txt_layer = Image.new('RGBA', image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)
    
    # 根据百分比调整字体大小
    min_dimension = min(image.width, image.height)
    
    # 调整字体大小比例，确保较长文字时字体较小
    adjusted_percent = font_size_percent
    if len(text) > 10:
        # 长文本降低字体大小
        adjusted_percent = max(3, font_size_percent * 7 / len(text))
        logger.debug(f"调整字体大小: 原始={font_size_percent}%, 调整后={adjusted_percent:.1f}%")
    
    font_size = int(min_dimension * adjusted_percent / 100)
    logger.debug(f"计算的字体大小: {font_size}px (图片最小边长的{adjusted_percent:.1f}%)")
    
    # 尝试加载中文字体
    font = None
    font_path = None
    
    # 中文字体优先级列表
    chinese_fonts = [
        FONT_PATH,  # 我们下载的思源黑体
        "C:\\Windows\\Fonts\\simhei.ttf",  # Windows 黑体
        "C:\\Windows\\Fonts\\msyh.ttc",    # Windows 微软雅黑
        "C:\\Windows\\Fonts\\simkai.ttf",  # Windows 楷体
        "C:\\Windows\\Fonts\\simsun.ttc",  # Windows 宋体
    ]
    
    # 尝试加载中文字体
    for path in chinese_fonts:
        try:
            if os.path.exists(path):
                font = ImageFont.truetype(path, font_size)
                font_path = path
                logger.debug(f"成功加载中文字体: {path}")
                break
        except Exception as e:
            logger.warning(f"加载中文字体失败 {path}: {str(e)}")
    
    # 如果所有中文字体都加载失败，尝试加载默认字体
    if font is None:
        try:
            font = ImageFont.load_default()
            logger.warning("加载默认字体，可能不支持中文")
        except Exception as e:
            logger.error(f"加载默认字体失败: {str(e)}")
            return jsonify({'success': False, 'error': '加载字体失败'})
    
    # 计算文字大小
    try:
        # 尝试使用getbbox (PIL 9.2.0+)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        logger.debug(f"文字大小 (getbbox): 宽度={text_width}, 高度={text_height}")
    except AttributeError:
        try:
            # 尝试使用getsize (旧版本PIL)
            text_width, text_height = draw.textsize(text, font=font)
            logger.debug(f"文字大小 (getsize): 宽度={text_width}, 高度={text_height}")
        except Exception as e:
            # 如果都失败，使用估计值
            text_width = font_size * len(text)
            text_height = font_size
            logger.warning(f"估计文字大小: 宽度={text_width}, 高度={text_height}")
    
    # 如果宽度为0，使用估计值（可能是某些字体测量问题）
    if text_width == 0:
        text_width = font_size * len(text)
        logger.warning(f"文字宽度为0，使用估计值: {text_width}")
    
    # 确保文字大小不超过图片大小
    if text_width > image.width * 0.9 or text_height > image.height * 0.5:
        # 如果文字太大，则适当缩小字体大小
        scale_factor = min(image.width * 0.9 / text_width, image.height * 0.5 / text_height)
        new_font_size = int(font_size * scale_factor)
        logger.debug(f"文字太大，缩小字体: {font_size} -> {new_font_size}px")
        
        # 重新加载字体并计算大小
        try:
            font = ImageFont.truetype(font_path or "arial.ttf", new_font_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            logger.debug(f"调整后文字大小: 宽度={text_width}, 高度={text_height}")
        except Exception as e:
            logger.error(f"调整字体大小失败: {str(e)}")

    # 创建更优美的水印布局
    try:
        # 根据图片尺寸确定水印网格尺寸
        # 目标是图片上最多显示15-25个水印
        target_watermarks = min(20, max(12, image.width * image.height // 250000))
        
        # 计算水印间距比例，根据图片大小和字体大小调整
        width_ratio = image.width / 1000  # 相对于1000px宽度的比例
        height_ratio = image.height / 1000  # 相对于1000px高度的比例
        size_ratio = min(width_ratio, height_ratio)
        
        # 水印间距系数
        spacing_factor = 1.8  # 固定间距系数，适合大多数情况
        
        # 根据图片尺寸计算水印网格
        image_area = image.width * image.height
        watermark_area = text_width * text_height * spacing_factor * spacing_factor
        
        # 计算图片可以容纳的水印数量
        watermarks_per_row = max(2, int(image.width / (text_width * spacing_factor)))
        watermarks_per_col = max(2, int(image.height / (text_height * spacing_factor)))
        
        # 计算水印的间距
        h_gap = image.width / watermarks_per_row
        v_gap = image.height / watermarks_per_col
        
        logger.debug(f"水印布局: {watermarks_per_col}行 x {watermarks_per_row}列, 水平间距={h_gap:.1f}px, 垂直间距={v_gap:.1f}px")
        
        # 水印起始偏移，使边缘水印不会太靠近边缘
        h_offset = max(10, (h_gap - text_width) / 2)
        v_offset = max(10, (v_gap - text_height) / 2)
        
        # 绘制水印
        watermarks_drawn = 0
        
        # 动态调整水印排布密度
        for row in range(watermarks_per_col):
            for col in range(watermarks_per_row):
                # 计算水印位置
                x = col * h_gap + h_offset
                y = row * v_gap + v_offset
                
                # 交错模式：奇数行偏移半个间距
                if row % 2 == 1:
                    x += h_gap / 2
                
                # 确保水印在图像范围内
                if x >= 0 and y >= 0 and x + text_width <= image.width and y + text_height <= image.height:
                    try:
                        draw.text((x, y), text, font=font, fill=(r, g, b, int(255 * opacity)))
                        watermarks_drawn += 1
                    except Exception as e:
                        logger.error(f"绘制水印错误 at ({x}, {y}): {str(e)}")
        
        # 如果没有绘制任何水印，尝试单水印模式
        if watermarks_drawn == 0:
            # 中心单水印
            x = (image.width - text_width) // 2
            y = (image.height - text_height) // 2
            draw.text((x, y), text, font=font, fill=(r, g, b, int(255 * opacity)))
            watermarks_drawn = 1
            logger.debug("使用中心单水印模式")
            
        logger.debug(f"已绘制 {watermarks_drawn} 个水印")
            
    except Exception as e:
        logger.error(f"绘制水印错误: {str(e)}")
        return jsonify({'success': False, 'error': '绘制水印失败'})
    
    # 如果角度不为0，旋转水印层
    if angle != 0:
        try:
            logger.debug(f"旋转水印层 {angle}度")
            # 创建一个足够大的画布，以容纳旋转后的图像
            diagonal = int((image.width**2 + image.height**2)**0.5)
            padded = Image.new('RGBA', (diagonal, diagonal), (0, 0, 0, 0))
            
            # 将水印层粘贴到中心
            paste_x = (diagonal - txt_layer.width) // 2
            paste_y = (diagonal - txt_layer.height) // 2
            padded.paste(txt_layer, (paste_x, paste_y), txt_layer)
            
            # 旋转画布
            rotated = padded.rotate(angle, resample=Image.BICUBIC, expand=False)
            
            # 裁剪回原始大小
            crop_x = (diagonal - image.width) // 2
            crop_y = (diagonal - image.height) // 2
            txt_layer = rotated.crop((crop_x, crop_y, crop_x + image.width, crop_y + image.height))
            
            logger.debug("成功旋转水印")
        except Exception as e:
            logger.error(f"旋转水印错误: {str(e)}")
    
    # 如果原图没有Alpha通道，添加一个
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    # 合并图层
    try:
        watermarked = Image.alpha_composite(image, txt_layer)
        logger.debug("成功合并水印层")
    except Exception as e:
        logger.error(f"合并水印层错误: {str(e)}")
        return jsonify({'success': False, 'error': '合并水印层失败'})
    
    # 保存结果
    result_filename = f"{uuid.uuid4()}.png"
    result_path = os.path.join(RESULT_FOLDER, result_filename)
    
    try:
        watermarked.save(result_path)
        logger.debug(f"成功保存水印图片: {result_path}")
    except Exception as e:
        logger.error(f"保存水印图片错误: {str(e)}")
        return jsonify({'success': False, 'error': '保存水印图片失败'})
    
    # 返回处理后的图片URL
    return jsonify({
        'success': True,
        'image_url': f'/static/results/{result_filename}'
    })

@app.route('/static/results/<filename>')
def result_file(filename):
    return send_from_directory(RESULT_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)