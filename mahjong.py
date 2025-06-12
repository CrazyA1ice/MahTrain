import pygame
import sys
import random
import time
from pygame.locals import *

# 初始化pygame
pygame.init()
pygame.font.init()

# 初始化图片资源
def load_tile_images():
    tile_images = {}
    for suit in ["万", "筒", "条"]:
        for number in range(1, 10):
            try:
                img_path = f"assets/tiles/{suit}{number}.png"
                image = pygame.image.load(img_path)
                tile_images[(suit, number)] = pygame.transform.scale(image, (70, 100))
            except:
                print(f"无法加载图片: {img_path}")
                # 使用默认绘制作为后备
                tile_images[(suit, number)] = None
    return tile_images

# 加载图片资源
TILE_IMAGES = load_tile_images()

# 麻将牌图形类
class Tile:
    def __init__(self, suit, number):
        self.suit = suit
        self.number = number
        self.width = 70
        self.height = 100
        self.selected = False
        self.image = TILE_IMAGES.get((suit, number))
        
    def draw(self, surface, x, y):
        if self.image:
            # 使用图片绘制
            surface.blit(self.image, (x, y))
            if self.selected:
                # 绘制选中高亮边框
                pygame.draw.rect(surface, HIGHLIGHT, (x, y, self.width, self.height), width=3, border_radius=8)
        else:
            if self.suit == "万":
                # 图片加载失败时使用默认绘制
                color = HIGHLIGHT if self.selected else TILE_COLOR
                pygame.draw.rect(surface, color, (x, y, self.width, self.height), border_radius=8)
                pygame.draw.rect(surface, TILE_BORDER, (x, y, self.width, self.height), width=3, border_radius=8)
                
                # 简单文字作为后备
                text = font_medium.render(f"{self.number}{self.suit}", True, (30, 30, 30))
                surface.blit(text, (x + self.width//2 - text.get_width()//2, 
                                y + self.height//2 - text.get_height()//2))
                # 万牌分为上下两部分
                num_text = ["一", "二", "三", "四", "五", "六", "七", "八", "九"][self.number-1]
                wan_text = "萬"
                
                # 上部数字（红色）
                top_text = font_small.render(num_text, True, (200, 30, 30))
                surface.blit(top_text, (x + self.width//2 - top_text.get_width()//2, y + 20))
                
                # 下部"萬"字（黑色）
                bottom_text = font_small.render(wan_text, True, (30, 30, 30))
                surface.blit(bottom_text, (x + self.width//2 - bottom_text.get_width()//2, y + 40))
            
            elif self.suit == "筒":  # 修复表达式错误
                # 筒牌精确绘制
                circle_radius = 10
                center_x = x + self.width // 2
                center_y = y + self.height // 2
                spacing = 21
                
                if self.number == 1:
                    # 一筒：正中一个大圈
                    pygame.draw.circle(surface, (30, 30, 30), (center_x, center_y), circle_radius)
                
                elif self.number == 2:
                    # 二筒：上下两个圈
                    pygame.draw.circle(surface, (30, 30, 30), (center_x, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x, center_y + spacing), circle_radius)
                
                elif self.number == 3:
                    # 三筒：左上到右下三个圈
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x, center_y), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y + spacing), circle_radius)
                
                elif self.number == 4:
                    # 四筒：两排每排各两个圈
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y + spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y + spacing), circle_radius)
                
                elif self.number == 5:
                    # 五筒：四筒基础上中间加一个圈
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x, center_y), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y + spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y + spacing), circle_radius)
                
                elif self.number == 6:
                    # 六筒：三排每排两个圈
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y + spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y + spacing), circle_radius)
                
                elif self.number == 7:
                    # 七筒：上面三个斜向排列(类似三筒)，下面四个(类似四筒)
                    # 精确调整位置和间距
                    #circle_radius = 8  # 进一步缩小圆圈半径
                    spacing = 20  # 增加间距
                    # 上面三个（整体上移并居中）
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing*0.8, center_y - spacing*1.0), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x, center_y - spacing*0.5), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing*0.8, center_y), circle_radius)
                    # 下面四个（整体下移并居中）
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing*0.8, center_y + spacing*0.8), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing*0.8, center_y + spacing*0.8), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing*0.8, center_y + spacing*1.6), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing*0.8, center_y + spacing*1.6), circle_radius)
                    # 恢复默认参数
                    #circle_radius = 10
                    #spacing = 15
                
                elif self.number == 8:
                    # 八筒：四排每排两个圈
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y - spacing*1.5), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y - spacing*1.5), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y - spacing/2), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y - spacing/2), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y + spacing/2), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y + spacing/2), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y + spacing*1.5), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y + spacing*1.5), circle_radius)
                
                elif self.number == 9:
                    # 九筒：三排每排各三个圈
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y - spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x, center_y), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x - spacing, center_y + spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x, center_y + spacing), circle_radius)
                    pygame.draw.circle(surface, (30, 30, 30), (center_x + spacing, center_y + spacing), circle_radius)
                
            elif self.suit == "条":
                # 条牌改为竖排显示
                bamboo_color = (0, 100, 0)
                center_x = x + self.width // 2
                if self.number == 1:
                    # 幺鸡特殊图案
                    pygame.draw.circle(surface, bamboo_color, (center_x, y + self.height//2), 15)
                else:
                    # 使用类似筒子牌的排布方式
                    circle_radius = 8
                    spacing = 15
                    if self.number == 2:
                        # 二条：上下两个竖条
                        pygame.draw.ellipse(surface, bamboo_color, 
                                        (center_x - 5, y + 15, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 5, y + 55, 10, 30))
                    elif self.number == 3:
                        # 三条：左中右三个竖条
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 20, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x, y + 20, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 20, 10, 30))
                    elif self.number == 4:
                        # 四条：四个角
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 15, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 5, y + 15, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 55, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 5, y + 55, 10, 30))
                    elif self.number == 5:
                        # 五条：四条加中间
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 15, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 5, y + 15, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 55, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 5, y + 55, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 5, y + 35, 10, 30))
                    elif self.number == 6:
                        # 六条：两排各三个
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 15, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x, y + 15, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 15, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 55, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x, y + 55, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 55, 10, 30))
                    elif self.number == 7:
                        # 七条：三加四
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 10, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x, y + 10, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 10, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 50, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 50, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 70, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 70, 10, 30))
                    elif self.number == 8:
                        # 八条：四排各两个
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 10, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 10, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 30, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 30, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 50, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 50, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 70, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 70, 10, 30))
                    elif self.number == 9:
                        # 九条：三排各三个
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 10, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x, y + 10, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 10, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 40, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x, y + 40, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 40, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x - 15, y + 70, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x, y + 70, 10, 30))
                        pygame.draw.ellipse(surface, bamboo_color,
                                        (center_x + 15, y + 70, 10, 30))

# 屏幕设置
WIDTH, HEIGHT = 1200, 900
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("四川麻将训练软件")

# 颜色定义
BACKGROUND = (40, 44, 52)
TILE_COLOR = (240, 240, 220)
TILE_BORDER = (180, 160, 140)
TILE_BACK_COLOR = (30, 60, 120)  # 麻将牌背面颜色(深蓝色)
TEXT_COLOR = (220, 220, 220)
HIGHLIGHT = (255, 215, 0)
BUTTON_COLOR = (70, 130, 180)
BUTTON_HOVER = (100, 149, 237)
PANEL_COLOR = (50, 54, 62)
RED = (220, 60, 60)
GREEN = (60, 180, 60)
BLUE = (70, 130, 180)
DIALOG_BG = (30, 35, 45)
DIALOG_BORDER = (100, 130, 180)

# 字体
title_font = pygame.font.SysFont('microsoftyahei', 48, bold=True)
font_large = pygame.font.SysFont('microsoftyahei', 32)
font_medium = pygame.font.SysFont('microsoftyahei', 24)
font_small = pygame.font.SysFont('microsoftyahei', 18)

# 麻将牌类型 - 只包含筒、条、万
SUITS = ["万", "筒", "条"]
NUMBERS = list(range(1, 10))

# 牌效训练模式
class TileEfficiencyTrainer:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.hand = self.generate_random_hand()
        self.sort_hand()  # 初始排序
        self.selected_tile = None
        self.message = "选择要打出的牌"
        self.message_color = TEXT_COLOR
        self.efficiency_score = self.calculate_efficiency()
        self.discard_history = []
        self.game_state = "ongoing"  # "ongoing", "win"
        self.show_win_dialog = False
        self.win_type = ""
        self.kongs = []  # 存储杠牌 [(suit, number)]
        
    def generate_random_hand(self):
        hand = []
        # 生成万、筒、条各36张（4套）
        for suit in SUITS:
            for number in NUMBERS:
                for _ in range(4):
                    hand.append((suit, number))
        random.shuffle(hand)
        return hand[:14]  # 四川麻将13张手牌
    
    def sort_hand(self):
        """按花色分组并从小到大排序"""
        # 按花色分组
        suits_dict = {"万": [], "筒": [], "条": []}
        for tile in self.hand:
            suit, value = tile
            suits_dict[suit].append(tile)
        
        # 对每个花色按数字排序
        for suit in suits_dict:
            suits_dict[suit] = sorted(suits_dict[suit], key=lambda x: x[1])
        
        # 按万、筒、条的顺序重新组合手牌
        self.hand = suits_dict["万"] + suits_dict["筒"] + suits_dict["条"]
    
    def calculate_efficiency(self):
        """计算当前手牌的牌效分数"""
        score = 0
        suits_count = {"万":0, "筒":0, "条":0}
        numbers = {"万":[], "筒":[], "条":[]}
        
        # 统计手牌中各花色的数量和数字
        for tile in self.hand:
            suit, value = tile
            suits_count[suit] += 1
            numbers[suit].append(value)
        
        # 计算缺门情况 - 四川麻将必须缺一门
        active_suits = [suit for suit in SUITS if suits_count[suit] > 0]
        if len(active_suits) == 2:
            score += 20  # 已缺一门，加分
        elif len(active_suits) == 1:
            score += 40  # 清一色潜力，更高加分
        
        # 计算同花色牌的数量得分
        for suit in SUITS:
            count = suits_count[suit]
            if count >= 6:
                score += 25  # 清一色潜力
            elif count >= 4:
                score += 15
            elif count >= 2:
                score += 5
                
        # 计算顺子潜力
        for suit in SUITS:
            num_list = sorted(numbers[suit])
            if not num_list:
                continue
                
            # 计算连张和坎张
            for i in range(len(num_list)-1):
                diff = num_list[i+1] - num_list[i]
                if diff == 0:
                    continue  # 相同牌，后面会单独计算对子
                elif diff == 1:
                    score += 8  # 连张
                elif diff == 2:
                    score += 5  # 坎张
            
            # 计算顺子
            i = 0
            while i < len(num_list)-2:
                if num_list[i] + 1 == num_list[i+1] and num_list[i+1] + 1 == num_list[i+2]:
                    score += 15  # 完整顺子
                    i += 3
                else:
                    i += 1
        
        # 计算对子/刻子
        tile_count = {}
        for tile in self.hand:
            key = f"{tile[0]}{tile[1]}"
            tile_count[key] = tile_count.get(key, 0) + 1
        
        for count in tile_count.values():
            if count == 2:
                score += 10  # 对子
            elif count == 3:
                score += 25  # 刻子
            elif count == 4:
                score += 40  # 杠
        
        return int(score)
    
    def discard_tile(self, tile):
        """打出一张牌并摸一张新牌"""
        if tile in self.hand:
            self.discard_history.append(tile)
            self.hand.remove(tile)
            
            # 从牌堆摸一张新牌
            new_tile = self.generate_random_tile()
            self.hand.append(new_tile)
            
            # 重新排序手牌
            self.sort_hand()
            
            # 重新计算牌效
            self.efficiency_score = self.calculate_efficiency()
            
            self.message = f"打出: {tile[1]}{tile[0]} → 摸到: {new_tile[1]}{new_tile[0]}"
            self.message_color = GREEN
            
            # 每次摸牌后强制检查胡牌条件
            self.game_state = "win" if self.check_win(self.hand) else "ongoing"
            if self.game_state == "win":
                self.win_type = "七对子" if self.is_seven_pairs(self.get_tile_count()) else "普通胡牌"
                self.show_win_dialog = False  # 重置对话框状态
        else:
            self.message = "错误: 该牌不在手牌中"
            self.message_color = RED
    
    def get_tile_count(self):
        """统计每种牌的数量"""
        tile_count = {}
        for tile in self.hand:
            key = f"{tile[0]}{tile[1]}"
            tile_count[key] = tile_count.get(key, 0) + 1
        return tile_count
    
    def check_win(self, hand):
        """检查是否胡牌"""
        # 检查是否已缺一门
        suits_in_hand = set(tile[0] for tile in hand)
        if len(suits_in_hand) == 3:
            return False  # 未缺一门，不能胡牌
        
        # 检查牌数是否合法
        if len(hand) != 14:
            return False
        
        tile_count = self.get_tile_count()
        
        # 检查七对子
        if self.is_seven_pairs(tile_count):
            return True
        
        # 检查普通胡牌（4个面子+1对将）
        if self.is_normal_win(tile_count):
            return True
        
        return False

    def kong(self):
        """开杠操作"""
        tile_count = self.get_tile_count()
        for tile_key, count in tile_count.items():
            if count == 4:
                # 找到四张相同的牌
                suit = tile_key[0]
                number = int(tile_key[1])
                kong_tile = (suit, number)
                
                # 从手牌中移除这四张牌
                self.hand = [t for t in self.hand if t != kong_tile]
                
                # 将杠牌存入kongs列表
                self.kongs.append(kong_tile)
                
                # 摸一张新牌
                new_tile = self.generate_random_tile()
                self.hand.append(new_tile)
                
                # 重新排序手牌
                self.sort_hand()
                
                # 重新计算牌效
                self.efficiency_score = self.calculate_efficiency()
                
                self.message = f"开杠: {number}{suit} → 摸到: {new_tile[1]}{new_tile[0]}"
                self.message_color = GREEN
                
                # 检查是否可以胡牌
                if self.check_win(self.hand):
                    self.game_state = "win"
                    self.win_type = "七对子" if self.is_seven_pairs(self.get_tile_count()) else "普通胡牌"
                
                return True
        
        self.message = "错误: 没有可以开杠的牌"
        self.message_color = RED
        return False
    
    def is_seven_pairs(self, tile_count):
        """检查是否是七对子胡牌"""
        pairs = 0
        for count in tile_count.values():
            if count == 2:
                pairs += 1
            elif count == 4:  # 杠也可以算作两个对子
                pairs += 2
        return pairs == 7
    
    def is_normal_win(self, tile_count):
        """检查普通胡牌（4个面子+1对将），考虑多种组合可能"""
        # 将牌统计转换为列表
        tiles = []
        for key, count in tile_count.items():
            suit = key[0]
            number = int(key[1])
            tiles.extend([(suit, number)] * count)
        
        # 按花色分组
        suits_dict = {"万": [], "筒": [], "条": []}
        for tile in tiles:
            suit, number = tile
            suits_dict[suit].append(number)
        
        # 对每个花色排序
        for suit in suits_dict:
            suits_dict[suit].sort()
        
        # 检查所有可能的组合
        return self._check_win_combination(suits_dict)
    
    def _check_win_combination(self, suits_dict, melds=0, pair_found=False):
        """递归检查所有可能的胡牌组合"""
        # 基本情况：已找到4个面子和1个对子
        if melds == 4 and pair_found:
            return True
            
        # 遍历所有花色
        for suit in SUITS:
            numbers = suits_dict[suit]
            if not numbers:
                continue
                
            # 检查刻子
            if len(numbers) >= 3 and numbers[0] == numbers[1] == numbers[2]:
                # 尝试作为刻子
                new_numbers = numbers[3:]
                new_suits_dict = suits_dict.copy()
                new_suits_dict[suit] = new_numbers
                if self._check_win_combination(new_suits_dict, melds + 1, pair_found):
                    return True
                    
            # 检查顺子
            if len(numbers) >= 3:
                first = numbers[0]
                if first + 1 in numbers and first + 2 in numbers:
                    # 尝试作为顺子
                    new_numbers = numbers.copy()
                    new_numbers.remove(first)
                    new_numbers.remove(first + 1)
                    new_numbers.remove(first + 2)
                    new_suits_dict = suits_dict.copy()
                    new_suits_dict[suit] = new_numbers
                    if self._check_win_combination(new_suits_dict, melds + 1, pair_found):
                        return True
                        
            # 检查对子
            if not pair_found and len(numbers) >= 2 and numbers[0] == numbers[1]:
                # 尝试作为对子
                new_numbers = numbers[2:]
                new_suits_dict = suits_dict.copy()
                new_suits_dict[suit] = new_numbers
                if self._check_win_combination(new_suits_dict, melds, True):
                    return True
                    
        return False
    
    def _check_melds(self, numbers, required_melds):
        """检查剩余牌是否能组成所需数量的面子"""
        melds = 0
        i = 0
        while i < len(numbers) - 2:
            # 检查顺子
            if numbers[i]+1 in numbers and numbers[i]+2 in numbers:
                melds += 1
                i += 3
            # 检查刻子
            elif i + 2 < len(numbers) and numbers[i] == numbers[i+1] == numbers[i+2]:
                melds += 1
                i += 3
            else:
                i += 1
        return melds >= required_melds
    
    def _count_melds(self, numbers):
        """计算面子数量"""
        melds = 0
        i = 0
        while i < len(numbers) - 2:
            # 检查顺子
            if numbers[i]+1 in numbers and numbers[i]+2 in numbers:
                melds += 1
                i += 3
            # 检查刻子
            elif numbers[i] == numbers[i+1] == numbers[i+2]:
                melds += 1
                i += 3
            else:
                i += 1
        return melds
    
    def _has_pair(self, numbers):
        """检查是否有对子"""
        i = 0
        while i < len(numbers) - 1:
            if numbers[i] == numbers[i+1]:
                return True
            i += 1
        return False
    
    def generate_random_tile(self):
        """生成一张随机牌，但不会与已有牌重复超过4张"""
        # 统计当前所有牌的数量
        all_tiles = []
        for suit in SUITS:
            for number in NUMBERS:
                all_tiles.append((suit, number))
        
        # 统计每种牌的数量
        tile_count = {}
        for tile in self.hand:
            key = (tile[0], tile[1])
            tile_count[key] = tile_count.get(key, 0) + 1
        
        # 移除已经达到4张的牌
        available_tiles = [tile for tile in all_tiles if tile_count.get(tile, 0) < 4]
        
        if not available_tiles:
            return random.choice(all_tiles)
        return random.choice(available_tiles)

# AI对战模式
class AIGame:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.player_hand = []
        self.ai_hands = [[], [], []]  # 三个AI玩家
        self.discards = []  # 格式: [("player"/"ai1"/"ai2"/"ai3", tile)]
        self.current_player = "player"  # "player", "ai1", "ai2", "ai3"
        self.message = "游戏开始"
        self.message_color = TEXT_COLOR
        self.game_state = "ongoing"  # "ongoing", "player_win", "ai1_win", "ai2_win", "ai3_win"
        self.win_type = ""  # 胡牌类型
        self.show_win_dialog = False  # 是否显示胡牌对话框
        self.deal_hands()
    
    def sort_player_hand(self):
        """按花色分组并从小到大排序玩家手牌"""
        # 按花色分组
        suits_dict = {"万": [], "筒": [], "条": []}
        for tile in self.player_hand:
            suit, value = tile
            suits_dict[suit].append(tile)
        
        # 对每个花色按数字排序
        for suit in suits_dict:
            suits_dict[suit] = sorted(suits_dict[suit], key=lambda x: x[1])
        
        # 按万、筒、条的顺序重新组合手牌
        self.player_hand = suits_dict["万"] + suits_dict["筒"] + suits_dict["条"]
    
    def deal_hands(self):
        """发牌(四玩家)"""
        all_tiles = []
        for suit in SUITS:
            for number in NUMBERS:
                for _ in range(4):
                    all_tiles.append((suit, number))
        
        random.shuffle(all_tiles)
        # 玩家和3个AI各13张牌
        self.player_hand = all_tiles[:13]
        self.ai_hands[0] = all_tiles[13:26]
        self.ai_hands[1] = all_tiles[26:39]
        self.ai_hands[2] = all_tiles[39:52]
        self.sort_player_hand()  # 初始排序玩家手牌
        self.discards = []
    
    def player_discard(self, tile):
        """玩家打出一张牌"""
        if self.game_state != "ongoing" or self.current_player != "player":
            self.message = "现在不是你的回合"
            self.message_color = RED
            return
            
        if tile in self.player_hand:
            self.player_hand.remove(tile)
            self.discards.append(("player", tile))
            self.message = f"你打出: {tile[1]}{tile[0]}"
            self.message_color = GREEN
            
            # 检查玩家是否胡牌
            if self.check_win(self.player_hand):
                self.game_state = "player_win"
                self.message = "恭喜! 你胡牌了!"
                self.message_color = HIGHLIGHT
                self.show_win_dialog = True
                return
            
            # 轮转到AI1
            self.current_player = "ai1"
            pygame.time.delay(1000)  # 等待1秒
            self.ai_turn()
        else:
            self.message = "错误: 该牌不在手牌中"
            self.message_color = RED
    
    def ai_turn(self):
        """AI回合"""
        if self.game_state != "ongoing" or self.current_player not in ["ai1", "ai2", "ai3"]:
            return
            
        # 确定当前AI玩家索引
        ai_index = int(self.current_player[2]) - 1
        current_ai_hand = self.ai_hands[ai_index]
        
        # AI摸牌
        new_tile = self.generate_random_tile(current_ai_hand)
        current_ai_hand.append(new_tile)
        
        # 检查AI是否胡牌
        if self.check_win(current_ai_hand):
            self.game_state = f"ai{ai_index+1}_win"
            self.message = f"AI{ai_index+1}胡牌了!"
            self.message_color = RED
            self.show_win_dialog = True
            return
        
        # AI选择一张牌打出
        discard_tile = self.ai_choose_discard(current_ai_hand)
        current_ai_hand.remove(discard_tile)
        self.discards.append((f"ai{ai_index+1}", discard_tile))
        
        self.message = f"AI{ai_index+1}打出: {discard_tile[1]}{discard_tile[0]}"
        self.message_color = TEXT_COLOR
        
        # 轮转到下一个玩家
        if self.current_player == "ai1":
            self.current_player = "ai2"
        elif self.current_player == "ai2":
            self.current_player = "ai3"
        else:  # ai3
            self.current_player = "player"
        
        # 如果是玩家回合则排序手牌
        if self.current_player == "player":
            self.sort_player_hand()
    
    def ai_choose_discard(self, hand):
        """AI选择要打出的牌（简化版）
        hand: 当前AI玩家的手牌
        """
        # 统计每种牌的数量
        tile_count = {}
        for tile in hand:
            key = f"{tile[0]}{tile[1]}"
            tile_count[key] = tile_count.get(key, 0) + 1
        
        # 优先打出手牌最少的花色
        suits_count = {"万":0, "筒":0, "条":0}
        for tile in hand:
            suits_count[tile[0]] += 1
        
        # 找到最少的非零花色
        min_suit = min([s for s in suits_count.keys() if suits_count[s] > 0], key=lambda s: suits_count[s])
        
        # 从最少的牌中选择一张最不可能组成顺子或刻子的牌
        candidate_tiles = [t for t in hand if t[0] == min_suit]
        
        if not candidate_tiles:
            # 如果该花色没有牌，则选择一张孤张
            for tile in self.ai_hand:
                key = f"{tile[0]}{tile[1]}"
                if tile_count[key] == 1:
                    return tile
            return random.choice(self.ai_hand)
        
        # 选择最不可能组成顺子的牌（边缘牌）
        numbers = [t[1] for t in candidate_tiles]
        sorted_numbers = sorted(numbers)
        
        # 优先打出边缘牌（1或9）
        if 1 in sorted_numbers:
            return (min_suit, 1)
        if 9 in sorted_numbers:
            return (min_suit, 9)
        
        # 其次打出与其他牌间隔大的牌
        max_diff = 0
        discard_candidate = candidate_tiles[0]
        for i in range(len(sorted_numbers)-1):
            diff = sorted_numbers[i+1] - sorted_numbers[i]
            if diff > max_diff:
                max_diff = diff
                discard_candidate = (min_suit, sorted_numbers[i])
        
        return discard_candidate
    
    def generate_random_tile(self, hand):
        """生成一张随机牌，但不会与已有牌重复超过4张"""
        # 统计当前所有牌的数量
        all_tiles = []
        for suit in SUITS:
            for number in NUMBERS:
                all_tiles.append((suit, number))
        
        # 统计每种牌的数量
        tile_count = {}
        for tile in hand + [d[1] for d in self.discards]:
            key = (tile[0], tile[1])
            tile_count[key] = tile_count.get(key, 0) + 1
        
        # 移除已经达到4张的牌
        available_tiles = [tile for tile in all_tiles if tile_count.get(tile, 0) < 4]
        
        if not available_tiles:
            return random.choice(all_tiles)
        return random.choice(available_tiles)
    
    def check_win(self, hand):
        """检查是否胡牌"""
        # 检查是否已缺一门
        suits_in_hand = set(tile[0] for tile in hand)
        if len(suits_in_hand) == 3:
            return False  # 未缺一门，不能胡牌
        
        # 检查牌数是否合法
        if len(hand) != 14:
            return False
        
        # 统计每种牌的数量
        tile_count = {}
        for tile in hand:
            key = f"{tile[0]}{tile[1]}"
            tile_count[key] = tile_count.get(key, 0) + 1
        
        # 检查七对子
        if self.is_seven_pairs(tile_count):
            self.win_type = "七对子"
            return True
        
        # 检查普通胡牌（4个面子+1对将）
        if self.is_normal_win(tile_count):
            self.win_type = "普通胡牌"
            return True
        
        return False
    
    def is_seven_pairs(self, tile_count):
        """检查是否是七对子胡牌"""
        # 七对子要求7个对子
        pairs = 0
        for count in tile_count.values():
            if count == 2:
                pairs += 1
            elif count == 4:  # 杠也可以算作两个对子
                pairs += 2
        
        return pairs == 7
    
    def is_normal_win(self, tile_count):
        """检查普通胡牌（4个面子+1对将）"""
        # 将牌统计转换为列表
        tiles = []
        for key, count in tile_count.items():
            suit = key[0]
            number = int(key[1])
            for _ in range(count):
                tiles.append((suit, number))
        
        # 按花色分组
        suits_dict = {"万": [], "筒": [], "条": []}
        for tile in tiles:
            suit, number = tile
            suits_dict[suit].append(number)
        
        # 对每个花色排序
        for suit in suits_dict:
            suits_dict[suit] = sorted(suits_dict[suit])
        
        # 检查每个花色的牌是否能组成面子
        melds = 0
        pair_found = False
        
        for suit in SUITS:
            numbers = suits_dict[suit]
            if not numbers:
                continue
                
            i = 0
            while i < len(numbers):
                # 检查刻子
                if i + 2 < len(numbers) and numbers[i] == numbers[i+1] == numbers[i+2]:
                    melds += 1
                    i += 3
                # 检查顺子
                elif i + 2 < len(numbers) and numbers[i] + 1 in numbers and numbers[i] + 2 in numbers:
                    # 移除顺子
                    if numbers[i] + 1 in numbers[i+1:] and numbers[i] + 2 in numbers[i+1:]:
                        melds += 1
                        # 找到并移除顺子的三个数字
                        num1 = numbers[i]
                        num2 = num1 + 1
                        num3 = num1 + 2
                        numbers.remove(num1)
                        numbers.remove(num2)
                        numbers.remove(num3)
                    else:
                        i += 1
                # 检查对子（将）
                elif not pair_found and i + 1 < len(numbers) and numbers[i] == numbers[i+1]:
                    pair_found = True
                    i += 2
                else:
                    i += 1
        
        # 检查是否找到4个面子和1个对子
        return melds == 4 and pair_found

# 游戏主类
class SichuanMahjongTrainer:
    def __init__(self):
        self.mode = "menu"  # "menu", "efficiency", "ai_game"
        self.efficiency_trainer = TileEfficiencyTrainer()
        self.ai_game = AIGame()
        self.buttons = {
            "efficiency": pygame.Rect(WIDTH//2-150, HEIGHT//2-60, 300, 50),
            "ai_game": pygame.Rect(WIDTH//2-150, HEIGHT//2+20, 300, 50),
            "back": pygame.Rect(50, HEIGHT-70, 120, 50),
            "reset": pygame.Rect(WIDTH-170, HEIGHT-70, 120, 50),
            "sort": pygame.Rect(WIDTH-170, HEIGHT-140, 120, 50),
            "ok": pygame.Rect(WIDTH//2-60, HEIGHT//2+50, 120, 40)  # 确认按钮
        }
        self.show_win_dialog = False
        self.win_message = ""
    
    def draw_menu(self):
        # 绘制标题
        title = title_font.render("四川麻将训练软件", True, HIGHLIGHT)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))
        
        # 绘制模式选择按钮
        pygame.draw.rect(screen, BUTTON_COLOR, self.buttons["efficiency"])
        pygame.draw.rect(screen, BUTTON_COLOR, self.buttons["ai_game"])
        
        eff_text = font_large.render("牌效训练", True, TEXT_COLOR)
        ai_text = font_large.render("AI对战", True, TEXT_COLOR)
        
        screen.blit(eff_text, (self.buttons["efficiency"].centerx - eff_text.get_width()//2, 
                              self.buttons["efficiency"].centery - eff_text.get_height()//2))
        screen.blit(ai_text, (self.buttons["ai_game"].centerx - ai_text.get_width()//2, 
                             self.buttons["ai_game"].centery - ai_text.get_height()//2))
        
        # 绘制规则提示
        rules = [
            "四川麻将规则:",
            "1. 只有筒、条、万三种花色，共108张牌",
            "2. 必须缺一门花色才能胡牌",
            "3. 不允许吃牌，只能碰或杠",
            "4. 胡牌需要14张牌（4个组合 + 1个对子）",
            "5. 点击'排序'按钮可以整理手牌",
            "6. 支持普通胡牌和七对子胡牌"
        ]
        
        for i, rule in enumerate(rules):
            text = font_small.render(rule, True, TEXT_COLOR)
            screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2 + 100 + i*25))
    
    def draw_efficiency_trainer(self):
        # 绘制标题
        title = title_font.render("牌效训练", True, HIGHLIGHT)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 30))
        
        # 绘制手牌
        hand = [Tile(tile[0], tile[1]) for tile in self.efficiency_trainer.hand]
        for tile in hand:
            tile.selected = (tile.suit, tile.number) == self.efficiency_trainer.selected_tile
        
        # 计算牌间距确保不重叠
        tile_spacing = 5
        total_width = sum(tile.width for tile in hand) + (len(hand)-1)*tile_spacing
        start_x = (WIDTH - total_width) // 2
        y_pos = HEIGHT // 2 - 100
        
        # 绘制花色分隔线提示
        suits = {"万": 0, "筒": 0, "条": 0}
        for tile in hand:
            suits[tile.suit] += 1
        
        x_pos = start_x
        for suit in SUITS:
            if suits[suit] > 0:
                pygame.draw.line(screen, HIGHLIGHT, 
                               (x_pos, y_pos - 10),
                               (x_pos, y_pos + hand[0].height + 10), 2)
                x_pos += suits[suit] * (hand[0].width + tile_spacing)
                pygame.draw.line(screen, HIGHLIGHT, 
                               (x_pos, y_pos - 10),
                               (x_pos, y_pos + hand[0].height + 10), 2)
        
        # 绘制牌
        x_pos = start_x
        for tile in hand:
            tile.draw(screen, x_pos, y_pos)
            x_pos += tile.width + tile_spacing
        
        # 绘制杠牌
        if self.efficiency_trainer.kongs:
            kong_y = HEIGHT - 150
            kong_start_x = WIDTH // 2 - 140
            
            # 绘制杠牌标签
            kong_label = font_medium.render("杠牌:", True, TEXT_COLOR)
            screen.blit(kong_label, (kong_start_x - 80, kong_y + 30))
            
            for kong_tile in self.efficiency_trainer.kongs:
                # 使用Tile类统一绘制四张牌
                tile_width, tile_height = 35, 50
                
                # 绘制三张背面朝上的牌
                for i in range(3):
                    tile = Tile("", "")  # 创建空白牌用于背面
                    tile.width, tile.height = tile_width, tile_height
                    # 绘制背面
                    pygame.draw.rect(screen, TILE_BACK_COLOR, 
                                   (kong_start_x + i * 40, kong_y, tile_width, tile_height), 
                                   border_radius=5)
                    pygame.draw.rect(screen, TILE_BORDER, 
                                   (kong_start_x + i * 40, kong_y, tile_width, tile_height), 
                                   width=2, border_radius=5)
                
                # 绘制一张正面朝上的牌
                tile = Tile(kong_tile[0], kong_tile[1])
                tile.width, tile.height = tile_width, tile_height
                tile.draw(screen, kong_start_x + 120, kong_y)
                
                kong_start_x += 180
        
        # 检查是否有四张相同的牌(开杠)
        tile_count = self.efficiency_trainer.get_tile_count()
        can_kong = any(count == 4 for count in tile_count.values())
        
        # 绘制杠按钮
        if can_kong:
            kong_rect = pygame.Rect(WIDTH//2 - 60, y_pos + hand[0].height + 60, 120, 40)
            pygame.draw.rect(screen, BUTTON_COLOR, kong_rect, border_radius=8)
            pygame.draw.rect(screen, BUTTON_HOVER, kong_rect, width=2, border_radius=8)
            kong_text = font_medium.render("开杠", True, TEXT_COLOR)
            screen.blit(kong_text, (kong_rect.centerx - kong_text.get_width()//2, 
                                  kong_rect.centery - kong_text.get_height()//2))
        
        # 绘制牌效分数
        score_text = font_large.render(f"牌效分数: {self.efficiency_trainer.efficiency_score}", True, GREEN)
        screen.blit(score_text, (WIDTH//2 - score_text.get_width()//2, y_pos + hand[0].height + 30))
        
        # 绘制消息
        msg_text = font_medium.render(self.efficiency_trainer.message, True, self.efficiency_trainer.message_color)
        screen.blit(msg_text, (WIDTH//2 - msg_text.get_width()//2, y_pos + hand[0].height + 80))
        
        # 如果可以胡牌，显示和牌按钮
        if self.efficiency_trainer.game_state == "win":
            win_rect = pygame.Rect(WIDTH//2 - 60, y_pos + hand[0].height + 110, 120, 40)
            pygame.draw.rect(screen, BUTTON_COLOR, win_rect, border_radius=8)
            pygame.draw.rect(screen, BUTTON_HOVER, win_rect, width=2, border_radius=8)
            win_text = font_medium.render("和牌", True, TEXT_COLOR)
            screen.blit(win_text, (win_rect.centerx - win_text.get_width()//2, 
                                  win_rect.centery - win_text.get_height()//2))
            
            # 显示胡牌对话框
            if self.efficiency_trainer.show_win_dialog:
                self.draw_win_dialog("牌效训练", self.efficiency_trainer.win_type)
        
        # 绘制牌效分数
        score_text = font_large.render(f"牌效分数: {self.efficiency_trainer.efficiency_score}", True, GREEN)
        screen.blit(score_text, (WIDTH//2 - score_text.get_width()//2, y_pos + hand[0].height + 30))
        
        # 绘制消息
        msg_text = font_medium.render(self.efficiency_trainer.message, True, self.efficiency_trainer.message_color)
        screen.blit(msg_text, (WIDTH//2 - msg_text.get_width()//2, y_pos + hand[0].height + 80))
        
        # 绘制弃牌历史
        if self.efficiency_trainer.discard_history:
            discard_text = font_small.render("弃牌历史:", True, TEXT_COLOR)
            screen.blit(discard_text, (50, HEIGHT - 120))
            
            discards = ", ".join([f"{t[1]}{t[0]}" for t in self.efficiency_trainer.discard_history[-5:]])
            history_text = font_small.render(discards, True, TEXT_COLOR)
            screen.blit(history_text, (50, HEIGHT - 90))
        
        # 绘制按钮
        self.draw_common_buttons()
    
    def draw_ai_game(self):
        # 绘制标题
        title = title_font.render("AI对战", True, HIGHLIGHT)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 30))
        
        # 绘制玩家手牌(底部)
        player_hand = self.ai_game.player_hand
        tile_width, tile_height = 50, 75
        start_x = (WIDTH - len(player_hand) * (tile_width - 15)) // 2
        y_pos = HEIGHT - 100
        
        # 绘制玩家手牌
        for i, tile in enumerate(player_hand):
            x = start_x + i * (tile_width - 15)
            tile_rect = pygame.Rect(x, y_pos, tile_width, tile_height)
            
            # 绘制牌背景
            pygame.draw.rect(screen, TILE_COLOR, tile_rect, border_radius=6)
            pygame.draw.rect(screen, TILE_BORDER, tile_rect, width=2, border_radius=6)
            
            # 绘制牌面
            suit, number = tile
            number_text = font_medium.render(str(number), True, (30, 30, 30))
            suit_text = font_small.render(suit, True, (30, 30, 30))
            
            screen.blit(number_text, (x + tile_width//2 - number_text.get_width()//2, y_pos + 15))
            screen.blit(suit_text, (x + tile_width//2 - suit_text.get_width()//2, y_pos + 40))
        
        # 绘制AI手牌(顶部和两侧)
        ai_hand_width, ai_hand_height = 40, 60
        # AI1(顶部)
        ai1_hand = self.ai_game.ai_hands[0]
        ai1_start_x = (WIDTH - len(ai1_hand) * (ai_hand_width - 10)) // 2
        for i in range(len(ai1_hand)):
            x = ai1_start_x + i * (ai_hand_width - 10)
            pygame.draw.rect(screen, TILE_COLOR, (x, 50, ai_hand_width, ai_hand_height), border_radius=5)
            pygame.draw.rect(screen, TILE_BORDER, (x, 50, ai_hand_width, ai_hand_height), width=1, border_radius=5)
        
        # AI2(左侧)
        ai2_hand = self.ai_game.ai_hands[1]
        for i in range(len(ai2_hand)):
            y = 150 + i * (ai_hand_height - 15)
            pygame.draw.rect(screen, TILE_COLOR, (50, y, ai_hand_width, ai_hand_height), border_radius=5)
            pygame.draw.rect(screen, TILE_BORDER, (50, y, ai_hand_width, ai_hand_height), width=1, border_radius=5)
        
        # AI3(右侧)
        ai3_hand = self.ai_game.ai_hands[2]
        for i in range(len(ai3_hand)):
            y = 150 + i * (ai_hand_height - 15)
            pygame.draw.rect(screen, TILE_COLOR, (WIDTH - 90, y, ai_hand_width, ai_hand_height), border_radius=5)
            pygame.draw.rect(screen, TILE_BORDER, (WIDTH - 90, y, ai_hand_width, ai_hand_height), width=1, border_radius=5)
        
        # 绘制弃牌区(中央正方形)
        discard_size = 40
        center_x, center_y = WIDTH//2, HEIGHT//2
        if self.ai_game.discards:
            for i, (player, tile) in enumerate(self.ai_game.discards[-16:]):
                # 根据玩家确定位置
                if player == "player":  # 底部
                    x = center_x - 80 + (i % 4) * (discard_size + 5)
                    y = center_y + 40 + (i // 4) * (discard_size + 5)
                elif player == "ai1":  # 顶部
                    x = center_x - 80 + (i % 4) * (discard_size + 5)
                    y = center_y - 80 + (i // 4) * (discard_size + 5)
                elif player == "ai2":  # 左侧
                    x = center_x - 120 + (i % 4) * (discard_size + 5)
                    y = center_y - 20 + (i // 4) * (discard_size + 5)
                else:  # ai3 右侧
                    x = center_x + 40 + (i % 4) * (discard_size + 5)
                    y = center_y - 20 + (i // 4) * (discard_size + 5)
                
                # 绘制弃牌
                color = BLUE if player == "player" else RED
                pygame.draw.rect(screen, color, (x, y, discard_size, discard_size), border_radius=4)
                pygame.draw.rect(screen, TILE_BORDER, (x, y, discard_size, discard_size), width=1, border_radius=4)
                
                # 绘制牌面
                suit, number = tile
                number_text = font_small.render(str(number), True, (30, 30, 30))
                suit_text = font_small.render(suit, True, (30, 30, 30))
                
                screen.blit(number_text, (x + discard_size//2 - number_text.get_width()//2, y + 5))
                screen.blit(suit_text, (x + discard_size//2 - suit_text.get_width()//2, y + 20))
        
        # 绘制消息
        msg_text = font_medium.render(self.ai_game.message, True, self.ai_game.message_color)
        screen.blit(msg_text, (WIDTH//2 - msg_text.get_width()//2, HEIGHT//2))
        
        # 绘制当前回合指示器
        turn_text = font_medium.render(f"当前回合: {'你' if self.ai_game.current_player == 'player' else 'AI'}", True, 
                                     GREEN if self.ai_game.current_player == 'player' else RED)
        screen.blit(turn_text, (WIDTH//2 - turn_text.get_width()//2, HEIGHT//2 + 40))
        
        # 绘制游戏状态
        if self.ai_game.game_state == "player_win":
            win_text = font_large.render("恭喜! 你赢了!", True, HIGHLIGHT)
            screen.blit(win_text, (WIDTH//2 - win_text.get_width()//2, HEIGHT//2 - 60))
        elif self.ai_game.game_state == "ai_win":
            win_text = font_large.render("AI赢了! 继续努力!", True, RED)
            screen.blit(win_text, (WIDTH//2 - win_text.get_width()//2, HEIGHT//2 - 60))
        
        # 绘制按钮
        self.draw_common_buttons()
        
        # 绘制胡牌对话框
        if self.ai_game.show_win_dialog:
            self.draw_win_dialog()
    
    def draw_win_dialog(self, mode, win_type):
        """绘制胡牌对话框
        Args:
            mode: 模式名称 ("牌效训练" 或 "AI对战")
            win_type: 胡牌类型
        """
        # 绘制半透明背景遮罩
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # 半透明黑色
        screen.blit(overlay, (0, 0))
        
        dialog_width, dialog_height = 500, 300
        dialog_x = (WIDTH - dialog_width) // 2
        dialog_y = (HEIGHT - dialog_height) // 2
        
        # 绘制对话框背景
        pygame.draw.rect(screen, DIALOG_BG, (dialog_x, dialog_y, dialog_width, dialog_height), border_radius=15)
        pygame.draw.rect(screen, DIALOG_BORDER, (dialog_x, dialog_y, dialog_width, dialog_height), width=3, border_radius=15)
        
        # 绘制标题
        title = font_large.render("胡牌!", True, HIGHLIGHT)
        screen.blit(title, (dialog_x + (dialog_width - title.get_width()) // 2, dialog_y + 30))
        
        # 绘制胡牌类型
        win_type_text = font_medium.render(f"胡牌类型: {win_type}", True, GREEN)
        screen.blit(win_type_text, (dialog_x + (dialog_width - win_type_text.get_width()) // 2, dialog_y + 80))
        
        # 绘制玩家信息
        if self.ai_game.game_state == "player_win":
            player_text = font_medium.render("恭喜你胡牌了!", True, HIGHLIGHT)
        else:
            player_text = font_medium.render("AI胡牌了!", True, RED)
        screen.blit(player_text, (dialog_x + (dialog_width - player_text.get_width()) // 2, dialog_y + 130))
        
        # 绘制提示信息
        hint = font_small.render("点击'确认'按钮开始新游戏", True, TEXT_COLOR)
        screen.blit(hint, (dialog_x + (dialog_width - hint.get_width()) // 2, dialog_y + 180))
        
        # 绘制确认按钮
        pygame.draw.rect(screen, BUTTON_COLOR, self.buttons["ok"], border_radius=8)
        pygame.draw.rect(screen, BUTTON_HOVER, self.buttons["ok"], width=2, border_radius=8)
        ok_text = font_medium.render("确认", True, TEXT_COLOR)
        screen.blit(ok_text, (self.buttons["ok"].centerx - ok_text.get_width()//2, 
                             self.buttons["ok"].centery - ok_text.get_height()//2))
    
    def draw_common_buttons(self):
        # 绘制返回和重置按钮
        pygame.draw.rect(screen, BUTTON_COLOR, self.buttons["back"])
        pygame.draw.rect(screen, BUTTON_COLOR, self.buttons["reset"])
        # 绘制排序按钮
        pygame.draw.rect(screen, BUTTON_COLOR, self.buttons["sort"])
        
        back_text = font_medium.render("返回", True, TEXT_COLOR)
        reset_text = font_medium.render("重置", True, TEXT_COLOR)
        sort_text = font_medium.render("排序", True, TEXT_COLOR)
        
        screen.blit(back_text, (self.buttons["back"].centerx - back_text.get_width()//2, 
                              self.buttons["back"].centery - back_text.get_height()//2))
        screen.blit(reset_text, (self.buttons["reset"].centerx - reset_text.get_width()//2, 
                               self.buttons["reset"].centery - reset_text.get_height()//2))
        screen.blit(sort_text, (self.buttons["sort"].centerx - sort_text.get_width()//2, 
                               self.buttons["sort"].centery - sort_text.get_height()//2))
    
    def kong(self):
        """开杠操作"""
        tile_count = self.get_tile_count()
        for tile_key, count in tile_count.items():
            if count == 4:
                # 找到四张相同的牌
                suit = tile_key[0]
                number = int(tile_key[1])
                kong_tile = (suit, number)
                
                # 从手牌中移除这四张牌
                self.hand = [t for t in self.hand if t != kong_tile]
                
                # 摸一张新牌
                new_tile = self.generate_random_tile()
                self.hand.append(new_tile)
                
                # 重新排序手牌
                self.sort_hand()
                
                # 重新计算牌效
                self.efficiency_score = self.calculate_efficiency()
                
                self.message = f"开杠: {number}{suit} → 摸到: {new_tile[1]}{new_tile[0]}"
                self.message_color = GREEN
                
                # 检查是否可以胡牌
                if self.check_win(self.hand):
                    self.game_state = "win"
                    self.win_type = "七对子" if self.is_seven_pairs(self.get_tile_count()) else "普通胡牌"
                
                return True
        
        self.message = "错误: 没有可以开杠的牌"
        self.message_color = RED
        return False

    def handle_click(self, pos):
        # 处理胡牌对话框的确认按钮
        if (self.ai_game.show_win_dialog or (self.mode == "efficiency" and self.efficiency_trainer.game_state == "win")) and self.buttons["ok"].collidepoint(pos):
            if self.mode == "ai_game":
                self.ai_game.reset()
            elif self.mode == "efficiency":
                self.efficiency_trainer.reset()
            return
        
        # 处理和牌按钮点击
        if self.mode == "efficiency" and self.efficiency_trainer.game_state == "win":
            hand = [Tile(tile[0], tile[1]) for tile in self.efficiency_trainer.hand]
            y_pos = HEIGHT // 2 - 100
            win_rect = pygame.Rect(WIDTH//2 - 60, y_pos + hand[0].height + 110, 120, 40)
            
            if win_rect.collidepoint(pos):
                # 显示胡牌对话框
                self.efficiency_trainer.show_win_dialog = True
                return
        
        # 处理开杠按钮点击
        if self.mode == "efficiency":
            hand = [Tile(tile[0], tile[1]) for tile in self.efficiency_trainer.hand]
            y_pos = HEIGHT // 2 - 100
            kong_rect = pygame.Rect(WIDTH//2 - 60, y_pos + hand[0].height + 60, 120, 40)
            
            if kong_rect.collidepoint(pos):
                self.efficiency_trainer.kong()
                return
        
        # 处理其他按钮点击
        if self.buttons["back"].collidepoint(pos):
            self.mode = "menu"
            self.ai_game.show_win_dialog = False
            return
        
        if self.buttons["reset"].collidepoint(pos):
            if self.mode == "efficiency":
                self.efficiency_trainer.reset()
            elif self.mode == "ai_game":
                self.ai_game.reset()
            return
        
        # 新增排序按钮处理
        if self.buttons["sort"].collidepoint(pos):
            if self.mode == "efficiency":
                self.efficiency_trainer.sort_hand()
                self.efficiency_trainer.message = "手牌已排序"
                self.efficiency_trainer.message_color = GREEN
            elif self.mode == "ai_game":
                self.ai_game.sort_player_hand()
                self.ai_game.message = "手牌已排序"
                self.ai_game.message_color = GREEN
            return
        
        # 菜单模式
        if self.mode == "menu":
            if self.buttons["efficiency"].collidepoint(pos):
                self.mode = "efficiency"
                self.efficiency_trainer.reset()
            elif self.buttons["ai_game"].collidepoint(pos):
                self.mode = "ai_game"
                self.ai_game.reset()
        
        # 牌效训练模式
        elif self.mode == "efficiency":
            hand = [Tile(tile[0], tile[1]) for tile in self.efficiency_trainer.hand]
            for tile in hand:
                tile.selected = (tile.suit, tile.number) == self.efficiency_trainer.selected_tile
            
            # 计算牌间距确保不重叠
            tile_spacing = 5
            total_width = sum(tile.width for tile in hand) + (len(hand)-1)*tile_spacing
            start_x = (WIDTH - total_width) // 2
            y_pos = HEIGHT // 2 - 100
            
            # 检查点击
            x_pos = start_x
            for tile in hand:
                if (x_pos <= pos[0] <= x_pos + tile.width and 
                    y_pos <= pos[1] <= y_pos + tile.height):
                    self.efficiency_trainer.selected_tile = (tile.suit, tile.number)
                    self.efficiency_trainer.discard_tile((tile.suit, tile.number))
                    break
                x_pos += tile.width + tile_spacing
        
        # AI对战模式
        elif self.mode == "ai_game" and self.ai_game.current_player == "player" and self.ai_game.game_state == "ongoing":
            player_hand = self.ai_game.player_hand
            tile_width, tile_height = 50, 75
            start_x = (WIDTH - len(player_hand) * (tile_width - 15)) // 2
            y_pos = HEIGHT - 150
            
            for i, tile in enumerate(player_hand):
                x = start_x + i * (tile_width - 15)
                tile_rect = pygame.Rect(x, y_pos, tile_width, tile_height)
                
                if tile_rect.collidepoint(pos):
                    self.ai_game.player_discard(tile)
                    break

# 主游戏循环
def main():
    game = SichuanMahjongTrainer()
    clock = pygame.time.Clock()
    
    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键点击
                    game.handle_click(event.pos)
        
        # 绘制背景
        screen.fill(BACKGROUND)
        
        # 绘制当前模式
        if game.mode == "menu":
            game.draw_menu()
        elif game.mode == "efficiency":
            game.draw_efficiency_trainer()
        elif game.mode == "ai_game":
            game.draw_ai_game()
        
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()