document.addEventListener('DOMContentLoaded', function () {
    // 元素
    const imageInput = document.getElementById('imageInput');
    const watermarkText = document.getElementById('watermarkText');
    const fontSizeRange = document.getElementById('fontSizeRange');
    const fontSizeValue = document.getElementById('fontSizeValue');
    const opacityRange = document.getElementById('opacityRange');
    const opacityValue = document.getElementById('opacityValue');
    const colorPicker = document.getElementById('colorPicker');
    const angleRange = document.getElementById('angleRange');
    const angleValue = document.getElementById('angleValue');
    const imagePreview = document.getElementById('imagePreview');
    const downloadArea = document.getElementById('downloadArea');
    const downloadBtn = document.getElementById('downloadBtn');
    const loadingOverlay = document.getElementById('loadingOverlay');
    
    // 变量
    let selectedImage = null;
    let watermarkedImageUrl = null;
    let updateTimer = null;
    let isProcessing = false;
    
    // 事件监听器
    imageInput.addEventListener('change', handleImageSelect);
    watermarkText.addEventListener('input', debounceUpdate);
    fontSizeRange.addEventListener('input', handleFontSizeChange);
    opacityRange.addEventListener('input', handleOpacityChange);
    colorPicker.addEventListener('input', debounceUpdate);
    angleRange.addEventListener('input', handleAngleChange);
    
    // 处理图片选择
    function handleImageSelect(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        // 验证是否为图片
        if (!file.type.match('image.*')) {
            alert('请选择图片文件！');
            return;
        }
        
        const reader = new FileReader();
        reader.onload = function (readerEvent) {
            selectedImage = readerEvent.target.result;
            displayPreviewImage(selectedImage);
            
            // 如果已经输入了水印文字，立即应用水印
            if (watermarkText.value.trim() !== '') {
                applyWatermark();
            }
        };
        reader.readAsDataURL(file);
    }
    
    // 显示预览图片
    function displayPreviewImage(src, isWatermarked = false) {
        imagePreview.innerHTML = '';
        const img = document.createElement('img');
        img.src = src;
        imagePreview.appendChild(img);
        
        // 只有水印图片才显示下载按钮
        downloadArea.style.display = isWatermarked ? 'block' : 'none';
        if (isWatermarked) {
            downloadBtn.href = src;
        }
    }
    
    // 处理字体大小变化
    function handleFontSizeChange() {
        fontSizeValue.textContent = fontSizeRange.value;
        debounceUpdate();
    }
    
    // 处理不透明度变化
    function handleOpacityChange() {
        opacityValue.textContent = opacityRange.value;
        debounceUpdate();
    }
    
    // 处理角度变化
    function handleAngleChange() {
        angleValue.textContent = angleRange.value;
        debounceUpdate();
    }
    
    // 防抖更新函数
    function debounceUpdate() {
        if (updateTimer) {
            clearTimeout(updateTimer);
        }
        updateTimer = setTimeout(() => {
            if (validateForm()) {
                applyWatermark();
            }
        }, 300); // 300ms延迟，避免频繁请求
    }
    
    // 验证表单
    function validateForm() {
        return selectedImage && watermarkText.value.trim() !== '';
    }
    
    // 应用水印
    function applyWatermark() {
        if (!validateForm() || isProcessing) return;
        
        // 设置处理状态
        isProcessing = true;
        
        // 显示加载中
        loadingOverlay.style.display = 'flex';
        
        // 准备数据
        const data = {
            image: selectedImage,
            text: watermarkText.value.trim(),
            fontSize: fontSizeRange.value,
            opacity: opacityRange.value,
            color: colorPicker.value,
            angle: angleRange.value
        };
        
        // 发送请求
        fetch('/api/watermark', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('网络请求失败');
            }
            return response.json();
        })
        .then(result => {
            if (result.success) {
                // 添加时间戳避免浏览器缓存
                watermarkedImageUrl = result.image_url + '?t=' + new Date().getTime();
                displayPreviewImage(watermarkedImageUrl, true);
            } else {
                alert('添加水印失败: ' + (result.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('发生错误：' + error.message);
        })
        .finally(() => {
            loadingOverlay.style.display = 'none';
            isProcessing = false;
        });
    }
}); 