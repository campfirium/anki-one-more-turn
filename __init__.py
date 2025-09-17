import random
import os
from aqt import mw
from aqt.qt import *
from anki.hooks import wrap, addHook
from aqt.reviewer import Reviewer
from aqt.gui_hooks import reviewer_did_answer_card, state_did_undo, state_did_change
from aqt.qt import QFileDialog
import json
import time
import webbrowser
from aqt import gui_hooks
# 安全删除：优先回收站，失败则物理删除
def safe_delete_file(path):
    try:
        from send2trash import send2trash as _sdt
        _sdt(path)
    except Exception:
        if os.path.exists(path):
            os.remove(path)


# 加载设置
try:
    config = mw.addonManager.getConfig(__name__)
    if config is None:
        config = {}
except Exception:
    config = {}

# 初始化计数器
counter = 0
last_total = 0
last_counter = 0

# 以前的日语谚语列表已删除，现在使用配置中的自定义文本

# 创建计数器标签
counter_label = None

# 添加新的全局变量
popup_counter = 0
learned_counter = 0
long_trigger_points = []
short_trigger_points = []
next_long_trigger_index = 0
next_short_trigger_index = 0

# 配置已经在上面加载过了，不需要重复加载
# config = mw.addonManager.getConfig(__name__)  # 删除重复加载

# 只在必要时添加缺失的新参数，不覆盖现有配置
def ensure_config_keys():
    global config
    config_changed = False

    # 定义当前版本需要的所有参数及其默认值（根据正确界面截图）
    required_keys = {
        'short_cards_completed': 10,
        'short_auto_close': True,
        'short_auto_close_duration': 2000,  # 2秒 = 2000毫秒
        'short_use_text_popup': True,  # 添加缺失的关键配置项
        'short_font_size': 16,
        'short_custom_quotes': '+10 XP\nLEVEL UP!',
        'short_text_width': 1200,
        'short_text_height': 400,
        'short_text_offset_x': 0,
        'short_text_offset_y': 10,  # 10%
        'short_use_image_popup': False,
        'short_image_folder': '',
        'short_image_width': 2480,
        'short_image_height': 1620,
        'short_image_offset_x': 0,
        'short_image_offset_y': 0,
        'long_cards_completed': 50,
        'long_auto_close': True,
        'long_auto_close_duration': 5000,  # 5秒 = 5000毫秒
        'long_use_text_popup': True,  # 添加缺失的关键配置项
        'long_font_size': 24,
        'long_custom_quotes': 'Great oaks from little acorns grow.\nThe constant drip hollows the stone.\nFrom tiny sparks grow mighty flames.\nPatience is bitter, but its fruit is sweet.\nConsistency is the mother of mastery.',
        'long_text_width': 2400,
        'long_text_height': 600,
        'long_text_offset_x': 0,
        'long_text_offset_y': 10,  # 10%
        'long_use_image_popup': False,
        'long_image_folder': '',
        'long_image_width': 3920,
        'long_image_height': 2160,
        'long_image_offset_x': 0,
        'long_image_offset_y': 0
    }

    # 只添加缺失的键，不覆盖现有的
    for key, default_value in required_keys.items():
        if key not in config:
            config[key] = default_value
            config_changed = True

    # 如果有变化，保存配置
    if config_changed:
        try:
            mw.addonManager.writeConfig(__name__, config)
        except FileNotFoundError:
            # 如果meta.json文件不存在，静默忽略，这在插件初始化时是正常的
            pass
        except Exception:
            # 忽略其他配置写入错误，不影响插件正常运行
            pass

ensure_config_keys()

# 修改常量定义
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "image_history.json")
MAX_HISTORY_ENTRIES = 20

# 添加这些新函数
def load_image_history():
    """从文件加载历史记录"""
    global image_history
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                loaded_history = json.load(f)
                # 只保留仍然存在的文件
                image_history = [path for path in loaded_history if os.path.exists(path)]
    except Exception as e:
        print(f"加载历史记录失: {e}")
        image_history = []

def save_image_history():
    """保存历史记录到文件"""
    try:
        # 确保只保存存在的文件路径
        global image_history
        image_history = [path for path in image_history if os.path.exists(path)]
        
        # 保存到文件
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(image_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存历史记录失败: {e}")
        QMessageBox.warning(
            mw,
            "保存失败",
            f"保存历史记录时发生错误：\n{str(e)}",
            QMessageBox.StandardButton.Ok
        )

def add_to_image_history(path):
    """添加新的图片路径到历史记录"""
    global image_history
    if path not in image_history:
        image_history.insert(0, path)  # 添加到开头
        if len(image_history) > MAX_HISTORY_ENTRIES:
            image_history = image_history[:MAX_HISTORY_ENTRIES]  # 只保留前20个，不删除文件
        save_image_history()  # 保存到文件

def delete_image(path):
    """删除图片和历史记录"""
    try:
        os.remove(path)
        image_history.remove(path)
        save_image_history()  # 保存到文
        # 刷新对话框
        mw.imageHistoryDialog.close()
        show_image_history()
    except Exception as e:
        print(f"删除片败: {e}")

def generate_trigger_points():
    global long_trigger_points, short_trigger_points
    long_interval = config.get('long_cards_completed', 50)
    short_interval = config.get('short_cards_completed', 10)
    max_points = 100  # 可以根据需要调整

    long_trigger_points = list(range(long_interval, max_points * long_interval + 1, long_interval))
    short_trigger_points = list(range(short_interval, max_points * short_interval + 1, short_interval))

def update_counter():
    global learned_counter, counter_label, last_total, last_counter, next_long_trigger_index, next_short_trigger_index
    if counter_label:
        deck_id = mw.col.decks.current()['id']
        counts = mw.col.sched.counts(deck_id)
        new, learn, review = counts
        total = sum(counts)
        
        total_change = total - last_total
        if total_change < 0:
            learned_counter -= total_change  # 等同于 learned_counter += abs(total_change)
        
        last_total = total
        last_counter = learned_counter
        counter_label.setText(f"新卡片: {new} | 学习: {learn} | 复习: {review} | 总计: {total} | 已学习: {learned_counter}")
        print(f"计数器更新：learned_counter = {learned_counter}, total = {total}")  # 添加调试输出

        # 弹窗触发逻辑已移到check_popup_trigger函数

def check_popup_trigger():
    """延迟检查弹窗触发，确保卡片切换完成后再弹窗"""
    global learned_counter, next_long_trigger_index, next_short_trigger_index

    # 检查长间隔触发
    long_triggered = False
    if next_long_trigger_index < len(long_trigger_points) and learned_counter >= long_trigger_points[next_long_trigger_index]:
        show_quote(is_long_progress=True)
        next_long_trigger_index += 1
        long_triggered = True

    # 检查短间隔触发（只有在长间隔没有触发时才检查）
    if not long_triggered and next_short_trigger_index < len(short_trigger_points) and learned_counter >= short_trigger_points[next_short_trigger_index]:
        show_quote(is_long_progress=False)
        next_short_trigger_index += 1

def show_quote(is_long_progress=False):
    global popup_counter, last_shown_image

    # 检查是否启用了弹窗功能
    if is_long_progress:
        use_text_popup = config.get('long_use_text_popup', True)
        use_image_popup = config.get('long_use_image_popup', False)
    else:
        use_text_popup = config.get('short_use_text_popup', True)
        use_image_popup = config.get('short_use_image_popup', False)

    # 如果两种弹窗都没有启用，直接返回
    if not use_text_popup and not use_image_popup:
        return

    # 每次触发提示时增加 popup_counter
    popup_counter += 1

    # 读取配置（与当前版保持一致的键名与默认值）
    if is_long_progress:
        custom_quotes = config.get('long_custom_quotes', "+10 XP\nLEVEL UP!")
        popup_width = config.get('long_image_width', 3920)
        popup_height = config.get('long_image_height', 2160)
        x_offset = config.get('long_image_offset_x', 0)
        y_offset = config.get('long_image_offset_y', 0)
        auto_close = config.get('long_auto_close', True)
        auto_close_duration = config.get('long_auto_close_duration', 5000)
        use_images = config.get('long_use_image_popup', False)
        image_folder = config.get('long_image_folder', "")
    else:
        custom_quotes = config.get('short_custom_quotes', "+10 XP\nLEVEL UP!")
        popup_width = config.get('short_image_width', 2480)
        popup_height = config.get('short_image_height', 1620)
        x_offset = config.get('short_image_offset_x', 0)
        y_offset = config.get('short_image_offset_y', 0)
        auto_close = config.get('short_auto_close', True)
        auto_close_duration = config.get('short_auto_close_duration', 2000)
        use_images = config.get('short_use_image_popup', False)
        image_folder = config.get('short_image_folder', "")

    # 使用配置中的自定义文本（不再使用旧的日语默认列表）
    if custom_quotes:
        quotes = [q.strip() for q in custom_quotes.split('\n') if q.strip()]
        quote = random.choice(quotes) if quotes else "+10 XP\nLEVEL UP!"
    else:
        quote = "+10 XP\nLEVEL UP!"

    # 判断是否有图片可用
    image_path = None
    if use_images and image_folder and os.path.exists(image_folder):
        image_files = [f for f in os.listdir(image_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        if image_files:
            # 将文件名转为完整路径
            all_image_paths = [os.path.join(image_folder, f) for f in image_files]

            # 优先选择未在历史记录中的图片
            unshown_images = [path for path in all_image_paths if path not in image_history]

            if unshown_images:
                # 如果有未显示过的图片，从中随机选择
                candidate = random.choice(unshown_images)
            else:
                # 如果所有图片都显示过，从最旧的开始重新选择
                # 排除最近显示的几张图片，避免连续重复
                recent_count = min(len(image_history), len(all_image_paths) // 2)
                recent_images = image_history[:recent_count] if recent_count > 0 else []
                available_images = [path for path in all_image_paths if path not in recent_images]

                if available_images:
                    candidate = random.choice(available_images)
                else:
                    # 如果连这个逻辑都失败了，就从所有图片中随机选择
                    candidate = random.choice(all_image_paths)

            if os.path.exists(candidate):
                image_path = candidate

    # 创建对话框
    print(f"[DEBUG] image_path = {image_path}")
    if image_path:
        # 更新最近显示的图片信息（仅图片弹窗）
        last_shown_image['path'] = image_path
        last_shown_image['timestamp'] = time.time()
        # 添加到图片历史记录
        add_to_image_history(image_path)

        dialog = QDialog(mw)
        
        # 检测是否是全屏模式（根据尺寸判断）
        screen = QApplication.primaryScreen()
        screen_size = screen.geometry()
        scale_factor = screen.devicePixelRatio()
        adjusted_width = int(popup_width / scale_factor)
        adjusted_height = int(popup_height / scale_factor)
        
        # 如果弹窗尺寸接近屏幕尺寸（90%以上），认为是全屏模式
        is_fullscreen = (adjusted_width >= screen_size.width() * 0.9 or 
                        adjusted_height >= screen_size.height() * 0.9)
        
        if is_fullscreen:
            # 全屏模式：保持原有的无边框样式
            dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(0, 0, 0, 0)
        else:
            # 非全屏模式：1px半透明边框 + 双层阴影，"轻轻浮起"效果
            dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2c2c2c;
                    border-radius: 8px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }
            """)
            # 主阴影：柔和的8px阴影
            main_shadow = QGraphicsDropShadowEffect()
            main_shadow.setBlurRadius(8)
            main_shadow.setOffset(0, 2)
            main_shadow.setColor(QColor(0, 0, 0, 51))  # rgba(0,0,0,0.2)
            dialog.setGraphicsEffect(main_shadow)
            
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(0, 0, 0, 0)

        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        class RoundedLabel(QLabel):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.is_fullscreen = is_fullscreen
                
            def paintEvent(self, event):
                try:
                    painter = QPainter(self)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    pm = self.pixmap()
                    if pm and not pm.isNull():
                        print(f"原图尺寸: {pm.width()}x{pm.height()}, 控件尺寸: {self.width()}x{self.height()}")
                        scaled = pm.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                        print(f"缩放后尺寸: {scaled.width()}x{scaled.height()}")
                        print(f"是否全屏: {self.is_fullscreen}")
                        
                        # 测试：非全屏直接显示原图
                        if not self.is_fullscreen:
                            print(f"非全屏模式：直接绘制原图 {pm.width()}x{pm.height()}")
                            painter.drawPixmap(self.rect(), pm)
                        else:
                            # 全屏：使用原来的逻辑
                            if scaled.width() <= self.width() and scaled.height() <= self.height():
                                x = (self.width() - scaled.width()) // 2
                                y = (self.height() - scaled.height()) // 2
                                target_rect = QRect(x, y, scaled.width(), scaled.height())
                                painter.drawPixmap(target_rect, scaled)
                            else:
                                x = (scaled.width() - self.width()) // 2
                                y = (scaled.height() - self.height()) // 2
                                source_rect = QRect(x, y, self.width(), self.height())
                                painter.drawPixmap(self.rect(), scaled, source_rect)
                except Exception as e:
                    print(f"图片渲染错误: {e}")
                    # 渲染失败时绘制背景色避免黑屏
                    painter = QPainter(self)
                    painter.fillRect(self.rect(), QColor("#2c2c2c"))

        label = RoundedLabel()
        label.setPixmap(QPixmap(image_path))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        # Delete 仅在图片弹窗有效
        def on_delete():
            confirm = DeleteConfirmDialog(image_path, dialog)
            if confirm.exec() == QDialog.DialogCode.Accepted:
                try:
                    if image_path in image_history:
                        image_history.remove(image_path)
                        save_image_history()
                    safe_delete_file(image_path)
                    dialog.accept()
                except Exception as e:
                    print(f"删除图片失败: {e}")
                    QMessageBox.warning(
                        mw, "Delete Failed", f"Error deleting image:\n{str(e)}",
                        QMessageBox.StandardButton.Ok
                    )
        delete_shortcut = QShortcut(QKeySequence("Delete"), dialog)
        delete_shortcut.activated.connect(on_delete)

    else:
        # 文本弹窗 - 使用新的设置系统
        dialog = QDialog(mw)
        dialog.setWindowTitle(f"{popup_counter} HIT{'!' * popup_counter}")
        layout = QVBoxLayout(dialog)
        
        # 获取文本弹窗的具体设置
        text_width = config.get(f'{("long" if is_long_progress else "short")}_text_width', 1200 if not is_long_progress else 2400)
        text_height = config.get(f'{("long" if is_long_progress else "short")}_text_height', 400 if not is_long_progress else 600)
        font_size = config.get(f'{("long" if is_long_progress else "short")}_font_size', 24 if is_long_progress else 16)
        text_x_offset = config.get(f'{("long" if is_long_progress else "short")}_text_x_offset', 0)
        text_y_offset = config.get(f'{("long" if is_long_progress else "short")}_text_y_offset', 10)
        
        # 创建标签
        label = QLabel(quote)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setFont(QFont("Arial", font_size))
        layout.addWidget(label)
        m = layout.contentsMargins()
        layout.setContentsMargins(m.left(), max(0, m.top() - 10), m.right(), m.bottom() + 10)

        # 设置尺寸和位置 - 与图片弹窗一致：按 devicePixelRatio 换算
        screen = QApplication.primaryScreen()
        scale_factor = screen.devicePixelRatio()
        adjusted_text_width  = int(text_width  / scale_factor)
        adjusted_text_height = int(text_height / scale_factor)

        dialog.setFixedSize(adjusted_text_width, adjusted_text_height)

        screen_geometry = screen.geometry()
        screen_center_x = screen_geometry.x() + screen_geometry.width() // 2
        screen_center_y = screen_geometry.y() + screen_geometry.height() // 2
        offset_x = int(screen_geometry.width() * text_x_offset / 100)
        offset_y = int(screen_geometry.height() * text_y_offset / 100)

        dialog_x = screen_center_x - adjusted_text_width // 2 + offset_x
        dialog_y = screen_center_y - adjusted_text_height // 2 - offset_y
        dialog.move(dialog_x, dialog_y)



    # 统一定时器逻辑：自动关闭用设置时间，手动关闭用24小时
    timeout = auto_close_duration if auto_close else 86400000  # 24小时
    QTimer.singleShot(timeout, dialog.accept)
    
    # 任意键关闭功能
    class AnyKeyEventFilter(QObject):
        def __init__(self, dialog, is_image_popup=False):
            super().__init__()
            self.dialog = dialog
            self.is_image_popup = is_image_popup
            
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                # 图片弹窗：Delete键不关闭（用于删除），其他键关闭
                if self.is_image_popup and key == Qt.Key.Key_Delete:
                    return False  # 让Delete键正常处理
                # 其他所有键都关闭弹窗
                self.dialog.accept()
                return True  # 拦截事件，不传递给Anki
            return False
    
    # 安装事件过滤器
    event_filter = AnyKeyEventFilter(dialog, bool(image_path))
    dialog.installEventFilter(event_filter)

    # 公共：尺寸与位置（为图片弹窗复用之前的计算，文本弹窗使用自己的定位）
    if image_path:
        # 图片弹窗：使用之前计算的adjusted_width和adjusted_height
        dialog.setFixedSize(adjusted_width, adjusted_height)
        
        screen_geometry = screen.geometry()
        screen_center_x = screen_geometry.x() + screen_geometry.width() // 2
        screen_center_y = screen_geometry.y() + screen_geometry.height() // 2
        offset_x = int(screen_geometry.width() * x_offset / 100)
        offset_y = int(screen_geometry.height() * y_offset / 100)

        dialog_x = screen_center_x - adjusted_width // 2 + offset_x
        dialog_y = screen_center_y - adjusted_height // 2 - offset_y  # 保持当前版"正值上移"的约定
        dialog.move(dialog_x, dialog_y)

    # 统一使用模态对话框，避免按键穿透问题
    # 强制获取焦点，确保快捷键能正常工作
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    dialog.setFocus()
    # 使用exec()确保模态行为
    dialog.exec()

    mw.destroyed.connect(dialog.close)

def on_card_answered(reviewer, card, ease):
    # 先更新计数器，但延迟检查弹窗触发，让Anki完成卡片切换
    global learned_counter, next_long_trigger_index, next_short_trigger_index
    
    # 更新计数器（不触发弹窗）
    if counter_label:
        deck_id = mw.col.decks.current()['id']
        counts = mw.col.sched.counts(deck_id)
        new, learn, review = counts
        total = sum(counts)
        
        global last_total, last_counter
        
        total_change = total - last_total
        if total_change < 0:
            learned_counter -= total_change
        last_total = total
        last_counter = learned_counter
        counter_label.setText(f"新卡片: {new} | 学习: {learn} | 复习: {review} | 总计: {total} | 已学习: {learned_counter}")
        print(f"计数器更新：learned_counter = {learned_counter}, total = {total}")
    
    # 延迟50ms检查弹窗触发，让弹窗与卡片切换几乎同时出现
    QTimer.singleShot(50, check_popup_trigger)

def init_counter():
    global counter_label, last_total, last_counter
    if not counter_label:
        counter_label = QLabel()
        # 注释掉以下行来隐藏计数器面板
        # mw.statusBar().addPermanentWidget(counter_label)
    deck_id = mw.col.decks.current()['id']
    counts = mw.col.sched.counts(deck_id)
    last_total = sum(counts)
    last_counter = counter
    update_counter()
    print(f"初始化计数器：counter = {counter}, last_total = {last_total}")  # 添加调试输出

def cleanup_counter():
    global counter_label, counter
    if counter_label:
        # 注释掉以下行，因为我们不再将计数器添加到状态栏
        # mw.statusBar().removeWidget(counter_label)
        counter_label.deleteLater()
        counter_label = None
    counter = 0

# 使用新钩子
reviewer_did_answer_card.append(on_card_answered)

# 添加设置菜单
def on_settings():
    dialog = QDialog(mw)
    dialog.setWindowTitle("OneMoreTurn Settings")
    dialog.resize(1000, 600)  # 调整为合适大小
    
    layout = QVBoxLayout()
    
    # 创建水平布局来放置两列
    columns_layout = QHBoxLayout()
    
    # 短进度设置面板
    short_panel = create_settings_panel("short", "Short Progress")
    columns_layout.addWidget(short_panel)
    
    # 长进度设置面板
    long_panel = create_settings_panel("long", "Long Progress")
    columns_layout.addWidget(long_panel)
    
    layout.addLayout(columns_layout)

    # 保存按钮
    save_button = QPushButton("Save Settings")
    save_button.clicked.connect(lambda: save_panel_settings(dialog))
    layout.addWidget(save_button)

    # 添加关于区域
    about_section = create_about_section()
    layout.addWidget(about_section)

    dialog.setLayout(layout)
    dialog.exec()

def get_version_from_manifest():
    """从manifest.json读取版本号"""
    try:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            return manifest.get('version', '1.0.0')
    except Exception:
        return '1.0.0'

def create_about_section():
    """创建关于区域"""
    about_widget = QWidget()
    about_layout = QVBoxLayout(about_widget)
    about_layout.setContentsMargins(20, 10, 20, 10)

    # 分隔线
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    line.setStyleSheet("QFrame { color: #666666; }")
    about_layout.addWidget(line)

    # 关于信息布局
    info_layout = QHBoxLayout()

    # 版本信息和作者信息
    version = get_version_from_manifest()
    author_info = 'by Roamer (<a href="https://campfirium.info/" style="color: #4a9eff; text-decoration: none;">Campfirium</a>)'
    version_label = QLabel(f"OneMoreTurn v{version} {author_info}")
    version_label.setStyleSheet("QLabel { color: #888888; font-size: 11px; }")
    version_label.setOpenExternalLinks(False)
    version_label.linkActivated.connect(lambda link: webbrowser.open(link))
    info_layout.addWidget(version_label)

    info_layout.addStretch()

    # 链接区域
    links_layout = QHBoxLayout()
    links_layout.setSpacing(15)

    # 定义链接
    links = [
        ("Showcase", "https://youtu.be/ZQylyGdv7h8"),
        ("Feedback", "https://github.com/campfirium/anki-one-more-turn/issues"),
        ("Support", "https://campfirium.info/t/one-more-turn%EF%BC%9Acustomizable-pop-up-rewards-for-anki/666"),
        ("Source", "https://github.com/campfirium/anki-one-more-turn")
    ]

    def create_link_label(text, url):
        """创建可点击的链接标签"""
        label = QLabel(f'<a href="{url}" style="color: #4a9eff; text-decoration: none;">{text}</a>')
        label.setOpenExternalLinks(False)  # 禁用默认的链接打开行为
        label.linkActivated.connect(lambda link: webbrowser.open(link))
        label.setStyleSheet("QLabel { font-size: 11px; }")
        label.setCursor(Qt.CursorShape.PointingHandCursor)
        return label

    # 添加链接
    for text, url in links:
        link_label = create_link_label(text, url)
        links_layout.addWidget(link_label)

    info_layout.addLayout(links_layout)
    about_layout.addLayout(info_layout)

    # 设置深色/浅色模式兼容的样式
    about_widget.setStyleSheet("""
        QWidget {
            background-color: transparent;
        }
    """)

    return about_widget

def create_settings_panel(prefix, title):
    """创建设置面板"""
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setSpacing(8)  # 减少间距
    
    # 面板标题
    title_label = QLabel(title)
    title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
    layout.addWidget(title_label)
    
    # 公共设置
    common_group = create_compact_common_settings(prefix)
    layout.addWidget(common_group)
    
    # 文本弹窗设置
    text_group = create_compact_text_settings(prefix)
    layout.addWidget(text_group)
    
    # 图片弹窗设置
    image_group = create_compact_image_settings(prefix)
    layout.addWidget(image_group)
    
    # 设置高亮效果
    setup_simple_highlighting(text_group, image_group, prefix)
    
    layout.addStretch()  # 底部弹性空间
    return panel

def create_compact_common_settings(prefix):
    """创建紧凑的公共设置组"""
    group = QGroupBox("Common Settings")
    layout = QFormLayout()
    layout.setVerticalSpacing(6)  # 减少垂直间距
    
    # 卡片完成数和自动关闭放在一行
    top_layout = QHBoxLayout()
    
    # Cards Completed - 减半宽度
    top_layout.addWidget(QLabel("Cards Completed:"))
    cards_completed = QSpinBox()
    cards_completed.setRange(1, 1000)
    cards_completed.setValue(config.get(f'{prefix}_cards_completed', 50 if prefix == 'long' else 10))
    cards_completed.setObjectName(f'{prefix}_cards_completed')
    cards_completed.setFixedWidth(120)  # 减半宽度
    top_layout.addWidget(cards_completed)
    
    # 中间留空
    top_layout.addStretch()
    
    # Auto close - 格式改为 Auto close(5s)
    auto_close_layout = QHBoxLayout()
    auto_close_layout.setSpacing(0)  # 紧凑排列
    
    auto_close = QCheckBox("Auto close(s): ")
    auto_close.setChecked(config.get(f'{prefix}_auto_close', True))
    auto_close.setObjectName(f'{prefix}_auto_close')
    auto_close_layout.addWidget(auto_close)
    
    auto_close_duration = QSpinBox()
    auto_close_duration.setRange(1, 60)
    auto_close_duration.setValue(config.get(f'{prefix}_auto_close_duration', 5000) // 1000)
    auto_close_duration.setObjectName(f'{prefix}_auto_close_duration')
    auto_close_duration.setFixedWidth(120)  # 固定宽度
    auto_close_layout.addWidget(auto_close_duration)
    
    # auto_close_layout.addWidget(QLabel("s)"))
    
    top_layout.addLayout(auto_close_layout)
    
    layout.addRow(top_layout)
    
    group.setLayout(layout)
    return group

def create_compact_text_settings(prefix):
    """创建紧凑的文本设置组"""
    group = QGroupBox()
    layout = QFormLayout()
    layout.setVerticalSpacing(6)
    
    # 标题行 - Text Popup Settings 和 Font 设置
    title_layout = QHBoxLayout()
    use_text = QCheckBox("Text Popup Settings")
    use_text.setChecked(not config.get(f'{prefix}_use_image_popup', False))
    use_text.setFont(QFont("Arial", 10, QFont.Weight.Bold))
    title_layout.addWidget(use_text)
    title_layout.addStretch()
    
    # Font 设置移到标题行右侧
    title_layout.addWidget(QLabel("Font (pt):"))
    font_size = QSpinBox()
    font_size.setRange(8, 72)
    font_size.setValue(config.get(f'{prefix}_font_size', 24 if prefix == 'long' else 16))
    font_size.setObjectName(f'{prefix}_font_size')
    font_size.setFixedWidth(120)  # 与width一致
    title_layout.addWidget(font_size)
    
    layout.addRow(title_layout)
    
    # 自定义引用 - 直接显示文本框
    custom_quotes = QPlainTextEdit()
    custom_quotes.setPlainText(config.get(f'{prefix}_custom_quotes', "+10 XP\nLEVEL UP!"))
    custom_quotes.setFixedHeight(100)  # 5行高度
    custom_quotes.setObjectName(f'{prefix}_custom_quotes')
    layout.addRow(custom_quotes)
    
    # 尺寸设置 - 固定宽度对齐
    size_layout = QHBoxLayout()
    width_label = QLabel("Width:")
    width_label.setFixedWidth(60)  # 左对齐标签
    size_layout.addWidget(width_label)
    text_width = QSpinBox()
    text_width.setRange(100, 99999)  # 与图片弹窗保持一致的范围
    text_width.setValue(config.get(f'{prefix}_text_width', 2400 if prefix == 'long' else 1200))  
    text_width.setObjectName(f'{prefix}_text_width')
    text_width.setFixedWidth(120)  # 固定宽度对齐
    size_layout.addWidget(text_width)
    size_layout.addStretch()
    
    height_label = QLabel("Height:")
    height_label.setFixedWidth(60)  # 左对齐标签
    size_layout.addWidget(height_label)
    text_height = QSpinBox()
    text_height.setRange(100, 99999)  # 与图片弹窗保持一致的范围
    text_height.setValue(config.get(f'{prefix}_text_height', 600 if prefix == 'long' else 400))  
    text_height.setObjectName(f'{prefix}_text_height')
    text_height.setFixedWidth(120)  # 固定宽度对齐
    size_layout.addWidget(text_height)
    
    layout.addRow(size_layout)
    
    # 位置偏移 - 固定宽度对齐
    offset_layout = QHBoxLayout()
    offset_x_label = QLabel("Offset X:")
    offset_x_label.setFixedWidth(60)  # 左对齐标签
    offset_layout.addWidget(offset_x_label)
    text_x_offset = QSpinBox()
    text_x_offset.setRange(-100, 100)
    text_x_offset.setValue(config.get(f'{prefix}_text_x_offset', 0))
    text_x_offset.setObjectName(f'{prefix}_text_x_offset')
    text_x_offset.setSuffix("%")
    text_x_offset.setFixedWidth(120)  # 固定宽度对齐
    offset_layout.addWidget(text_x_offset)
    offset_layout.addStretch()
    
    offset_y_label = QLabel("Offset Y:")
    offset_y_label.setFixedWidth(60)  # 左对齐标签
    offset_layout.addWidget(offset_y_label)
    text_y_offset = QSpinBox()
    text_y_offset.setRange(-100, 100)
    text_y_offset.setValue(config.get(f'{prefix}_text_y_offset', 10))
    text_y_offset.setObjectName(f'{prefix}_text_y_offset')
    text_y_offset.setSuffix("%")
    text_y_offset.setFixedWidth(120)  # 固定宽度对齐
    offset_layout.addWidget(text_y_offset)
    
    layout.addRow(offset_layout)
    
    group.setLayout(layout)
    return group

def create_compact_image_settings(prefix):
    """创建紧凑的图片设置组"""
    group = QGroupBox()
    layout = QFormLayout()
    layout.setVerticalSpacing(6)
    
    # 启用图片模式的复选框作为标题
    use_images = QCheckBox("Image Popup Settings")
    use_images.setChecked(config.get(f'{prefix}_use_image_popup', False))
    use_images.setObjectName(f'{prefix}_use_image_popup')
    use_images.setFont(QFont("Arial", 10, QFont.Weight.Bold))
    layout.addRow(use_images)
    
    # 图片文件夹
    folder_layout = QHBoxLayout()
    folder_layout.addWidget(QLabel("Folder:"))
    image_folder = QLineEdit(config.get(f'{prefix}_image_folder', ""))
    image_folder.setObjectName(f'{prefix}_image_folder')
    image_folder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    folder_layout.addWidget(image_folder)
    
    choose_folder = QPushButton("...")
    choose_folder.setFixedWidth(30)
    choose_folder.clicked.connect(lambda: choose_image_folder(image_folder))
    folder_layout.addWidget(choose_folder)
    
    layout.addRow(folder_layout)
    
    # 尺寸设置 - 固定宽度对齐
    size_layout = QHBoxLayout()
    width_label = QLabel("Width:")
    width_label.setFixedWidth(60)  # 左对齐标签
    size_layout.addWidget(width_label)
    popup_width = QSpinBox()
    popup_width.setRange(100, 99999)
    popup_width.setValue(config.get(f'{prefix}_image_width', 3920 if prefix == 'long' else 2480))
    popup_width.setObjectName(f'{prefix}_image_width')
    popup_width.setFixedWidth(120)  # 固定宽度对齐
    size_layout.addWidget(popup_width)
    size_layout.addStretch()
    
    height_label = QLabel("Height:")
    height_label.setFixedWidth(60)  # 左对齐标签
    size_layout.addWidget(height_label)
    popup_height = QSpinBox()
    popup_height.setRange(100, 99999)
    popup_height.setValue(config.get(f'{prefix}_image_height', 2160 if prefix == 'long' else 1620))
    popup_height.setObjectName(f'{prefix}_image_height')
    popup_height.setFixedWidth(120)  # 固定宽度对齐
    size_layout.addWidget(popup_height)
    
    layout.addRow(size_layout)
    
    # 位置偏移 - 固定宽度对齐
    offset_layout = QHBoxLayout()
    offset_x_label = QLabel("Offset X:")
    offset_x_label.setFixedWidth(60)  # 左对齐标签
    offset_layout.addWidget(offset_x_label)
    x_offset = QSpinBox()
    x_offset.setRange(-100, 100)
    x_offset.setValue(config.get(f'{prefix}_image_offset_x', 0))
    x_offset.setObjectName(f'{prefix}_image_offset_x')
    x_offset.setSuffix("%")
    x_offset.setFixedWidth(120)  # 固定宽度对齐
    offset_layout.addWidget(x_offset)
    offset_layout.addStretch()
    
    offset_y_label = QLabel("Offset Y:")
    offset_y_label.setFixedWidth(60)  # 左对齐标签
    offset_layout.addWidget(offset_y_label)
    y_offset = QSpinBox()
    y_offset.setRange(-100, 100)
    y_offset.setValue(config.get(f'{prefix}_image_offset_y', 0))
    y_offset.setObjectName(f'{prefix}_image_offset_y')
    y_offset.setSuffix("%")
    y_offset.setFixedWidth(120)  # 固定宽度对齐
    offset_layout.addWidget(y_offset)
    
    layout.addRow(offset_layout)
    
    group.setLayout(layout)
    return group

def choose_image_folder(line_edit):
    """选择图片文件夹"""
    folder = QFileDialog.getExistingDirectory(
        None,
        "选择图片文件夹",
        line_edit.text()
    )
    if folder:
        line_edit.setText(folder)

def setup_simple_highlighting(text_group, image_group, prefix):
    """设置简单的高亮效果"""
    # 查找复选框
    use_text = None
    for checkbox in text_group.findChildren(QCheckBox):
        if checkbox.text() == "Text Popup Settings":
            use_text = checkbox
            break
    use_images = image_group.findChild(QCheckBox, f'{prefix}_use_image_popup')
    
    def update_highlighting():
        text_enabled = use_text.isChecked() if use_text else False
        image_enabled = use_images.isChecked() if use_images else False
        
        if text_enabled:
            text_group.setStyleSheet("QGroupBox { border: 2px solid #4CAF50; border-radius: 6px; }")
            image_group.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 6px; }")
            # 启用文本组，禁用图片组
            for widget in text_group.findChildren(QWidget):
                if hasattr(widget, 'setEnabled') and widget != use_text:
                    widget.setEnabled(True)
            for widget in image_group.findChildren(QWidget):
                if hasattr(widget, 'setEnabled') and widget != use_images:
                    widget.setEnabled(False)
        elif image_enabled:
            image_group.setStyleSheet("QGroupBox { border: 2px solid #2196F3; border-radius: 6px; }")
            text_group.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 6px; }")
            # 启用图片组，禁用文本组
            for widget in image_group.findChildren(QWidget):
                if hasattr(widget, 'setEnabled') and widget != use_images:
                    widget.setEnabled(True)
            for widget in text_group.findChildren(QWidget):
                if hasattr(widget, 'setEnabled') and widget != use_text:
                    widget.setEnabled(False)
        else:
            # 如果两个都没勾选，默认选择文本模式
            use_text.setChecked(True)
            return
    
    def on_text_toggled(checked):
        if checked:
            use_images.setChecked(False)
        update_highlighting()
    
    def on_image_toggled(checked):
        if checked:
            use_text.setChecked(False)
        update_highlighting()
    
    # 连接复选框信号
    if use_text:
        use_text.toggled.connect(on_text_toggled)
    if use_images:
        use_images.toggled.connect(on_image_toggled)
    
    # 初始化高亮状态
    update_highlighting()

def save_panel_settings(dialog):
    """保存面板设置"""
    # 查找所有面板
    for panel in dialog.findChildren(QWidget):
        if not hasattr(panel, 'layout'):
            continue
            
        # 遍历所有带objectName的控件
        for child in panel.findChildren(QWidget):
            obj_name = child.objectName()
            if not obj_name:
                continue
                
            # 处理不同类型的控件
            if isinstance(child, QSpinBox):
                if obj_name.endswith('_auto_close_duration'):
                    # auto_close_duration 需要从秒转换为毫秒
                    config[obj_name] = child.value() * 1000
                else:
                    config[obj_name] = child.value()
            elif isinstance(child, QCheckBox):
                config[obj_name] = child.isChecked()
            elif isinstance(child, QLineEdit):
                config[obj_name] = child.text()
            elif isinstance(child, QPlainTextEdit):
                config[obj_name] = child.toPlainText()


    # 写入配置文件
    try:
        mw.addonManager.writeConfig(__name__, config)
    except FileNotFoundError as e:
        # 如果meta.json文件不存在，尝试创建基本的meta.json文件
        try:
            addon_dir = os.path.dirname(__file__)
            meta_path = os.path.join(addon_dir, "meta.json")

            # 创建基本的meta.json结构
            meta_data = {
                "config": config,
                "disabled": False,
                "mod": 0,
                "conflicts": [],
                "max_point_version": 0,
                "min_point_version": 0,
                "branch_index": 0,
                "update_enabled": True
            }

            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, indent=2, ensure_ascii=False)

            # 再次尝试写入配置
            mw.addonManager.writeConfig(__name__, config)
        except Exception as write_error:
            # 如果仍然失败，显示错误信息但不阻止用户继续使用
            mw.utils.showWarning(f"Warning: Could not save settings to meta.json file. "
                               f"Settings may not persist after restart.\n\n"
                               f"Error: {str(write_error)}")
    except Exception as e:
        # 处理其他可能的写入错误
        mw.utils.showWarning(f"Warning: Could not save settings. "
                           f"Settings may not persist after restart.\n\n"
                           f"Error: {str(e)}")

    generate_trigger_points()  # 重新生成触发点
    dialog.accept()

action = QAction("OneMoreTurn Settings", mw)
action.triggered.connect(on_settings)
mw.form.menuTools.addAction(action)

# 确保复习开始时初始化计数器
addHook("showQuestion", init_counter)

# 添加 on_undo 数
def on_undo(col):
    global learned_counter, next_long_trigger_index, next_short_trigger_index, last_total, last_counter, popup_counter
    deck_id = mw.col.decks.current()['id']
    counts = mw.col.sched.counts(deck_id)
    total = sum(counts)
    
    # 如果总计增加,说明是撤销了一次学习作
    if total > last_total:
        learned_counter = max(0, learned_counter - 1)  # 减少已习数,但不小0
        # 需调整触发点索引,保持原样
    
    last_total = total
    last_counter = learned_counter
    
    update_counter()
    print(f"撤销操作后：learned_counter = {learned_counter}, next_long_trigger_index = {next_long_trigger_index}, next_short_trigger_index = {next_short_trigger_index}")  # 添加调试输出

# 用 gui_hooks 来监听销操作
state_did_undo.append(on_undo)

# 移除以行，因为我们不再用 mw.undo_action
# mw.undo_action.triggered.connect(on_undo)

def reset_counter():
    global learned_counter, next_long_trigger_index, next_short_trigger_index, last_total, last_counter, popup_counter
    learned_counter = 0
    next_long_trigger_index = 0
    next_short_trigger_index = 0
    popup_counter = 0  # 重置 popup_counter
    deck_id = mw.col.decks.current()['id']
    counts = mw.col.sched.counts(deck_id)
    last_total = sum(counts)
    last_counter = 0
    generate_trigger_points()  # 重新生成触发点
    update_counter()
    print(f"计数器已重置：learned_counter = {learned_counter}, popup_counter = {popup_counter}")

# 修改 on_state_change 函数
def on_state_change(new_state, old_state):
    if new_state == "overview" or new_state == "deckBrowser":
        print(f"进入{new_state}，重置计数器")  # 调输出
        reset_counter()
    elif new_state == "review":
        print(f"进入review状态")  # 调试输出

# 修改 check_hooks 函数
def check_hooks():
    print("检查钩子...")
    if on_state_change in state_did_change._hooks:
        print("state_change 钩子已正确加")
    else:
        print("警告：state_change 子未添加")

# 在件末尾添加以下代码
state_did_change.append(on_state_change)
addHook("profileLoaded", check_hooks)
addHook("reviewer_did_finish", reset_counter)

# 删除以下行，因为我们现在使用 state_did_change 来处理所状态变化
# addHook("overview", reset_counter)
# addHook("deckBrowser", reset_counter)

# 删除 on_deck_browser 函数和相关的子，因为我们现在使用 state_did_change 来处理这种情况

# 在适当的位置调用 generate_trigger_points()，例如在件加载时或设置更改后
generate_trigger_points()

class ImageSettingsWidget(QWidget):
    # 现有代码...
    
    def setup_ui(self):
        # ...现UI设置...
        
        # 改Choose Folder按钮的连接
        self.source_choose_folder_btn.clicked.connect(self.choose_source_folder)
        self.target_choose_folder_btn.clicked.connect(self.choose_target_folder)
        
    def choose_source_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择源图片文件夹",
            self.source_folder_edit.text()
        )
        if folder:
            self.source_folder_edit.setText(folder)
            
    def choose_target_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择目标图片文件夹",
            self.target_folder_edit.text()
        )
        if folder:
            self.target_folder_edit.setText(folder)

# 在现有代码中添加以下和变量

# 存储图片历史的列
image_history = []
MAX_HISTORY_ENTRIES = 20

def show_image_history():
    dialog = QDialog(mw)
    dialog.setWindowTitle("OneMoreTurn Image History")
    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowCloseButtonHint)
    
    layout = QVBoxLayout()
    layout.setSpacing(10)
    layout.setContentsMargins(30, 10, 30, 10)
    
    # 获取屏幕尺寸
    screen = QApplication.primaryScreen()
    screen_size = screen.size()
    
    # 设置对话框大小为屏幕的80%
    dialog_width = int(screen_size.width() * 0.8)
    dialog_height = int(screen_size.height() * 0.8)
    
    # 计算网格布局中的实际可用空间
    available_width = dialog_width - 60
    available_height = dialog_height - 40
    
    # 固定为5列4行布局
    columns = 5
    rows = 4
    
    # 计算单个容器的尺寸
    spacing = 20
    container_width = (available_width - (columns - 1) * spacing) // columns
    container_height = (available_height - (rows - 1) * spacing) // rows
    
    # 确保16:9的比例
    if container_width / 16 > container_height / 9:
        container_width = container_height * 16 // 9
    else:
        container_height = container_width * 9 // 16
    
    grid = QGridLayout()
    grid.setSpacing(spacing)
    grid.setContentsMargins(0, 0, 0, 0)
    
    class ImageLabel(QLabel):
        def __init__(self, image_path):
            super().__init__()
            self.image_path = image_path
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            
        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                print(f"Opening file: {self.image_path}")  # 调试输出
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.image_path))
    
        def paintEvent(self, event):
            if self.pixmap():
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                
                # 创建圆角路径
                path = QPainterPath()
                path.addRoundedRect(0, 0, self.width(), self.height(), 8, 8)
                painter.setClipPath(path)
                
                # 缩放图片并保持比例
                scaled_pixmap = self.pixmap().scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # 计算居中位置
                x = (scaled_pixmap.width() - self.width()) // 2
                y = (scaled_pixmap.height() - self.height()) // 2
                source_rect = QRect(x, y, self.width(), self.height())
                
                # 绘制图片
                painter.drawPixmap(self.rect(), scaled_pixmap, source_rect)
    
    # 填充格
    valid_images = [path for path in image_history if os.path.exists(path)]
    for row in range(rows):
        for col in range(columns):
            index = row * columns + col
            container = QWidget()
            container.setFixedSize(container_width, container_height)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            
            if index < len(valid_images):
                image_path = valid_images[index]
                
                # 创建图片容器
                image_container = QWidget()
                image_container_layout = QVBoxLayout(image_container)
                image_container_layout.setContentsMargins(0, 0, 0, 0)
                image_container_layout.setSpacing(0)
                
                # 添加图片标签
                image_label = ImageLabel(image_path)
                pixmap = QPixmap(image_path)
                scaled_pixmap = pixmap.scaled(
                    container_width,
                    container_height,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                image_label.setPixmap(scaled_pixmap)
                image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                image_container_layout.addWidget(image_label)
                
                # 创建悬浮层
                class OverlayWidget(QWidget):
                    def __init__(self, image_path, parent=None):
                        super().__init__(parent)
                        self.image_path = image_path
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
                    
                    def mousePressEvent(self, event):
                        if event.button() == Qt.MouseButton.LeftButton:
                            # 检查点击是否在删除按钮区域
                            pos = event.pos()
                            for child in self.children():
                                if isinstance(child, DeleteButton):
                                    if child.geometry().contains(pos):
                                        return  # 如果点在删除按钮上，不打开文件
                            # 否则打开文件
                            QDesktopServices.openUrl(QUrl.fromLocalFile(self.image_path))
                
                overlay = OverlayWidget(image_path, image_container)
                overlay.setFixedSize(container_width, container_height)
                overlay_layout = QVBoxLayout(overlay)
                overlay_layout.setContentsMargins(0, 0, 0, 0)  # 移除所有边距
                
                # 创建删除按钮
                delete_btn = DeleteButton(image_path)
                delete_btn.setText("×")
                delete_btn.setFixedSize(20, 20)
                delete_btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #999999;
                        border: none;
                        font-size: 14px;
                        font-weight: bold;
                        margin: 0px;
                    }
                    QPushButton:hover {
                        color: #ff4d4f;
                        background-color: transparent;
                    }
                """)
                
                # 创建按钮容器（靠右对齐）
                btn_container = QWidget()
                btn_layout = QHBoxLayout(btn_container)
                btn_layout.setContentsMargins(5, 5, 5, 0)  # 只保留顶部和两侧的边距
                btn_layout.addStretch()
                btn_layout.addWidget(delete_btn)
                
                # 添加文件名标签
                filename = os.path.splitext(os.path.basename(image_path))[0]
                filename_label = QLabel(filename)
                filename_label.setStyleSheet("""
                    QLabel {
                        background-color: rgba(0, 0, 0, 0.5);
                        color: #999999;
                        padding: 4px 0px;
                        font-size: 10px;
                        border-bottom-left-radius: 8px;  /* 添加底部圆角 */
                        border-bottom-right-radius: 8px;  /* 添加底部圆角 */
                    }
                """)
                filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                filename_label.setFixedWidth(container_width)  # 确保宽度与容器相同
                
                # 将按钮和文件名添加到悬浮层
                overlay_layout.addWidget(btn_container)
                overlay_layout.addStretch()
                overlay_layout.addWidget(filename_label, 0, Qt.AlignmentFlag.AlignBottom)  # 确保标签在底部
                
                # 初始隐藏悬浮层
                overlay.hide()
                
                # 添加鼠标事件处理
                def create_enter_event(overlay_widget):
                    def enter_event(event):
                        overlay_widget.show()
                    return enter_event
                
                def create_leave_event(overlay_widget):
                    def leave_event(event):
                        overlay_widget.hide()
                    return leave_event
                
                image_container.enterEvent = create_enter_event(overlay)
                image_container.leaveEvent = create_leave_event(overlay)
                
                container_layout.addWidget(image_container)
            
            grid.addWidget(container, row, col)
    
    layout.addLayout(grid)
    dialog.setLayout(layout)
    dialog.setStyleSheet("""
        QDialog { 
            background: #2c2c2c;
        }
        QLabel {
            background: transparent;
        }
    """)
    
    dialog.setFixedSize(dialog_width, dialog_height)
    dialog.setModal(True)
    
    mw.imageHistoryDialog = dialog
    dialog.exec()

# 添加定义的 ClickableLabel 类
class ClickableLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.path = ""
        
    def mousePressEvent(self, event):
        if self.path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))

# 修改 DeleteButton 类的实现
class DeleteButton(QPushButton):
    def __init__(self, path):
        super().__init__()
        self.path = path.replace('\\', '/')  # 统一使用正斜杠
        self.clicked.connect(self.on_click)
        
    def on_click(self):
        try:
            # 先从历史记录中移除
            if self.path in image_history:
                image_history.remove(self.path)
                save_image_history()
            
            # 然后删除文件
            try:
                import send2trash
                send2trash.send2trash(self.path)
            except:
                if os.path.exists(self.path):
                    os.remove(self.path)
            
            # 刷新图片历史对话框
            if hasattr(mw, 'imageHistoryDialog'):
                mw.imageHistoryDialog.close()
                show_image_history()
                
        except Exception as e:
            print(f"删除图片失败: {e}")

# 在插件加载时读取历史录
load_image_history()

# 修改菜单项标
history_action = QAction("OneMoreTurn Image History", mw)
history_action.triggered.connect(show_image_history)
mw.form.menuTools.addAction(history_action)

try:
    import send2trash
except Exception:
    send2trash = None
import send2trash

# 加新全局变量来跟踪最显示的图片
last_shown_image = {
    'path': None,
    'timestamp': None
}

class DeleteConfirmDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setWindowTitle("Delete Image")
        self.setup_ui()
        self.setup_shortcuts()  # 添加快捷键设置
        
    def setup_shortcuts(self):
        # 添加 Delete 键快捷键
        delete_shortcut = QShortcut(QKeySequence("Delete"), self)
        delete_shortcut.activated.connect(self.accept)
        
        # 添加 Enter/Return 键快捷键
        enter_shortcut = QShortcut(QKeySequence("Return"), self)
        enter_shortcut.activated.connect(self.accept)
        
        # 添加 Enter 小键盘快捷键
        enter_pad_shortcut = QShortcut(QKeySequence("Enter"), self)
        enter_pad_shortcut.activated.connect(self.accept)
        
        # 添加 Esc 键取消
        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.activated.connect(self.reject)
    
    def setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(160, 40, 160, 40)  # 将左边距从 80 增加到 160
        
        try:
            # 创建图片容器
            image_container = QWidget()
            image_container.setFixedSize(400, 225)  # 16:9 比例
            container_layout = QVBoxLayout(image_container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            
            # 添加图片预览
            class PreviewLabel(QLabel):
                def paintEvent(self, event):
                    if self.pixmap():
                        painter = QPainter(self)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                        
                        # 创建圆角路径
                        path = QPainterPath()
                        path.addRoundedRect(0, 0, self.width(), self.height(), 8, 8)
                        painter.setClipPath(path)
                        
                        # 缩放图片并保持比例
                        scaled_pixmap = self.pixmap().scaled(
                            self.size(),
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # 计算居中位置
                        x = (scaled_pixmap.width() - self.width()) // 2
                        y = (scaled_pixmap.height() - self.height()) // 2
                        source_rect = QRect(x, y, self.width(), self.height())
                        
                        # 绘制图片
                        painter.drawPixmap(self.rect(), scaled_pixmap, source_rect)
            
            preview_label = PreviewLabel()
            preview_label.setFixedSize(400, 225)
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                preview_label.setPixmap(pixmap)
                container_layout.addWidget(preview_label)
                
                # 添加文件名
                filename = os.path.basename(self.image_path)
                name_label = QLabel(filename)
                name_label.setStyleSheet("""
                    QLabel {
                        background-color: rgba(0, 0, 0, 0.5);
                        color: #999999;
                        padding: 4px 0px;
                        font-size: 10px;
                        border-bottom-left-radius: 8px;
                        border-bottom-right-radius: 8px;
                    }
                """)
                name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_label.setFixedWidth(400)
                container_layout.addWidget(name_label, 0, Qt.AlignmentFlag.AlignBottom)
                
                main_layout.addWidget(image_container, 0, Qt.AlignmentFlag.AlignCenter)
            else:
                print(f"Failed to load image preview: {self.image_path}")
        except Exception as e:
            print(f"Error loading preview image: {e}")
        
        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)  # 增加按钮之间的间距
        
        delete_btn = QPushButton("Delete")
        cancel_btn = QPushButton("Cancel")
        
        for btn in [delete_btn, cancel_btn]:
            btn.setFixedSize(120, 32)  # 调整按钮大小
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: #999999;
                    border: none;
                    border-radius: 6px;  # 增加圆角
                    padding: 5px 15px;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #454545;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
            """)
        
        delete_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        
        main_layout.addSpacing(30)  # 增加图片和按钮之间的间距
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)
        
        # 设置窗口样式
        self.setStyleSheet("""
            QDialog {
                background-color: #2c2c2c;
            }
        """)
        
        # 调整窗口大小
        self.setFixedSize(720, 380)  # 将宽度从 560 增加到 720，以适应更大的边距


