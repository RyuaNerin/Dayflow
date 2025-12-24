"""
Dayflow - 邮件推送服务
支持 QQ 邮箱定时发送效率报告，含 AI 点评功能
"""
import smtplib
import logging
import asyncio
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from dataclasses import dataclass

import config
from i18n import _

logger = logging.getLogger(__name__)

# 工作日活跃时长（小时）
DAILY_ACTIVE_HOURS = 16


@dataclass
class EmailConfig:
    """邮箱配置"""
    smtp_server: str = "smtp.qq.com"
    smtp_port: int = 465
    sender_email: str = ""
    auth_code: str = ""  # QQ邮箱授权码
    receiver_email: str = ""
    enabled: bool = False


class EmailService:
    """邮件服务"""
    
    def __init__(self, config: EmailConfig):
        self.config = config
    
    def send_report(self, subject: str, html_content: str) -> tuple:
        """发送 HTML 报告邮件，返回 (成功, 错误信息)"""
        if not self.config.enabled:
            return False, _("邮件推送未启用")
        
        if not all([self.config.sender_email, self.config.auth_code, self.config.receiver_email]):
            return False, _("邮箱配置不完整")
        
        try:
            # 创建邮件
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.sender_email
            msg["To"] = self.config.receiver_email
            
            # 添加 HTML 内容
            html_part = MIMEText(html_content, "html", "utf-8")
            msg.attach(html_part)
            
            # 发送邮件
            logger.info(f"正在连接 SMTP 服务器: {self.config.smtp_server}:{self.config.smtp_port}")
            server = smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port, timeout=30)
            try:
                logger.info("SMTP 连接成功，正在登录...")
                server.login(self.config.sender_email, self.config.auth_code)
                logger.info("登录成功，正在发送邮件...")
                server.sendmail(
                    self.config.sender_email,
                    self.config.receiver_email,
                    msg.as_string()
                )
                # sendmail 成功 = 邮件已发送
                logger.info(f"邮件发送成功: {subject}")
                return True, ""
            finally:
                # 忽略 quit() 时的错误（QQ 邮箱可能返回非标准响应）
                try:
                    server.quit()
                except Exception:
                    pass
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = _("授权码错误或SMTP服务未开启")
            logger.error(f"SMTP认证失败: {e}")
            return False, error_msg
        except smtplib.SMTPConnectError as e:
            error_msg = _("无法连接SMTP服务器，请检查网络")
            logger.error(f"SMTP连接失败: {e}")
            return False, error_msg
        except TimeoutError:
            error_msg = _("连接超时，请检查网络或端口是否被封锁")
            logger.error("SMTP连接超时")
            return False, error_msg
        except Exception as e:
            error_msg = str(e)
            logger.error(f"邮件发送失败: {e}")
            return False, error_msg


class DeepAnalyzer:
    """
    深度数据分析器 - 纯数据驱动，不做主观臆断
    
    注意：原始 cards 是每分钟一条记录（系统设计），需要合并成真正的工作段
    """
    
    def __init__(self, cards: list):
        self.cards = cards
        self.sorted_cards = sorted(
            [c for c in cards if c.start_time], 
            key=lambda x: x.start_time
        )
        # 合并连续同类型记录为真正的工作段
        self.merged_sessions = self._merge_consecutive_cards()
    
    def _merge_consecutive_cards(self) -> list:
        """
        将连续的同类型记录合并成真正的工作段
        
        例如：10个连续的"编程"卡片 → 1个10分钟的编程工作段
        
        注意：如果两张卡片之间的时间间隔超过 5 分钟，即使类别相同也视为不同工作段
        """
        if not self.sorted_cards:
            return []
        
        # 时间间隔阈值（分钟）- 超过此值视为不同工作段
        GAP_THRESHOLD_MINUTES = 5
        
        sessions = []
        current_session = {
            'category': self.sorted_cards[0].category,
            'start_time': self.sorted_cards[0].start_time,
            'end_time': self.sorted_cards[0].end_time,
            'duration': self.sorted_cards[0].duration_minutes,
            'scores': [self.sorted_cards[0].productivity_score] if self.sorted_cards[0].productivity_score > 0 else []
        }
        
        for card in self.sorted_cards[1:]:
            # 计算与上一张卡片的时间间隔
            time_gap = 0
            if current_session['end_time'] and card.start_time:
                time_gap = (card.start_time - current_session['end_time']).total_seconds() / 60
            
            # 如果类别相同且时间间隔在阈值内，合并到当前工作段
            if card.category == current_session['category'] and time_gap <= GAP_THRESHOLD_MINUTES:
                current_session['duration'] += card.duration_minutes
                current_session['end_time'] = card.end_time
                if card.productivity_score > 0:
                    current_session['scores'].append(card.productivity_score)
            else:
                # 类别不同或时间间隔过大，保存当前工作段，开始新的
                current_session['avg_score'] = int(sum(current_session['scores']) / len(current_session['scores'])) if current_session['scores'] else 0
                sessions.append(current_session)
                current_session = {
                    'category': card.category,
                    'start_time': card.start_time,
                    'end_time': card.end_time,
                    'duration': card.duration_minutes,
                    'scores': [card.productivity_score] if card.productivity_score > 0 else []
                }
        
        # 保存最后一个工作段
        current_session['avg_score'] = int(sum(current_session['scores']) / len(current_session['scores'])) if current_session['scores'] else 0
        sessions.append(current_session)
        
        return sessions
    
    def analyze(self) -> dict:
        """执行完整的深度分析，返回结构化数据"""
        return {
            'focus': self._analyze_focus(),
            'rhythm': self._analyze_rhythm(),
            'switching': self._analyze_switching(),
            'categories': self._analyze_categories(),
            'timeline': self._analyze_timeline(),
            'day_type': self._classify_day_type(),
            'raw_record_count': len(self.cards)  # 原始记录数（分钟数）
        }
    
    def _analyze_focus(self) -> dict:
        """专注力分析 - 基于合并后的真实工作段"""
        if not self.merged_sessions:
            return {'has_data': False}
        
        durations = [s['duration'] for s in self.merged_sessions if s['duration'] > 0]
        if not durations:
            return {'has_data': False}
        
        # 时长分布统计（基于真实工作段）
        fragments = [d for d in durations if d < 15]  # <15分钟
        short = [d for d in durations if 15 <= d < 30]  # 15-30分钟
        medium = [d for d in durations if 30 <= d < 60]  # 30-60分钟
        deep = [d for d in durations if d >= 60]  # >60分钟（深度工作）
        
        # 找最长的那次
        max_duration = max(durations)
        max_session = None
        for s in self.merged_sessions:
            if s['duration'] == max_duration:
                max_session = {
                    'category': s['category'],
                    'duration': int(max_duration),
                    'time': s['start_time'].strftime('%H:%M') if s['start_time'] else ''
                }
                break
        
        return {
            'has_data': True,
            'total_sessions': len(self.merged_sessions),  # 真实工作段数量
            'fragment_count': len(fragments),  # 碎片数量
            'fragment_percent': int(len(fragments) / len(durations) * 100) if durations else 0,
            'short_count': len(short),
            'medium_count': len(medium),
            'deep_count': len(deep),  # 深度工作次数
            'deep_total_mins': int(sum(deep)),  # 深度工作总时长
            'max_session': max_session,
            'avg_duration': int(sum(durations) / len(durations))
        }
    
    def _analyze_rhythm(self) -> dict:
        """工作节奏分析 - 按时段统计"""
        # 按小时统计
        hourly_data = {}
        for card in self.sorted_cards:
            if card.start_time and card.productivity_score > 0:
                hour = card.start_time.hour
                if hour not in hourly_data:
                    hourly_data[hour] = {'scores': [], 'minutes': 0}
                hourly_data[hour]['scores'].append(card.productivity_score)
                hourly_data[hour]['minutes'] += card.duration_minutes
        
        if not hourly_data:
            return {'has_data': False}
        
        # 计算每小时平均分
        hourly_avg = {h: int(sum(d['scores'])/len(d['scores'])) 
                      for h, d in hourly_data.items()}
        
        # 找峰值和谷值
        peak_hour = max(hourly_avg, key=hourly_avg.get)
        low_hour = min(hourly_avg, key=hourly_avg.get)
        
        # 按时段汇总
        periods = {
            _('上午(6-12)'): {'scores': [], 'minutes': 0},
            _('下午(12-18)'): {'scores': [], 'minutes': 0},
            _('晚上(18-24)'): {'scores': [], 'minutes': 0}
        }
        for hour, data in hourly_data.items():
            if 6 <= hour < 12:
                periods[_('上午(6-12)')]['scores'].extend(data['scores'])
                periods[_('上午(6-12)')]['minutes'] += data['minutes']
            elif 12 <= hour < 18:
                periods[_('下午(12-18)')]['scores'].extend(data['scores'])
                periods[_('下午(12-18)')]['minutes'] += data['minutes']
            else:
                periods[_('晚上(18-24)')]['scores'].extend(data['scores'])
                periods[_('晚上(18-24)')]['minutes'] += data['minutes']
        
        period_stats = {}
        for name, data in periods.items():
            if data['scores']:
                period_stats[name] = {
                    'avg_score': int(sum(data['scores'])/len(data['scores'])),
                    'total_mins': int(data['minutes']),
                    'session_count': len(data['scores'])
                }
        
        return {
            'has_data': True,
            'hourly_avg': hourly_avg,
            'peak_hour': peak_hour,
            'peak_score': hourly_avg[peak_hour],
            'low_hour': low_hour,
            'low_score': hourly_avg[low_hour],
            'periods': period_stats
        }
    
    def _analyze_switching(self) -> dict:
        """任务切换分析 - 基于合并后的真实工作段"""
        if len(self.merged_sessions) < 2:
            return {'has_data': False, 'total_switches': 0}
        
        # 切换次数 = 工作段数量 - 1
        switches = []
        for i in range(1, len(self.merged_sessions)):
            prev = self.merged_sessions[i-1]
            curr = self.merged_sessions[i]
            switches.append({
                'time': curr['start_time'].strftime('%H:%M') if curr['start_time'] else '',
                'from': prev['category'],
                'to': curr['category']
            })
        
        # 统计切换频率
        from collections import Counter
        switch_pairs = Counter(f"{s['from']}→{s['to']}" for s in switches)
        most_common = switch_pairs.most_common(3)
        
        return {
            'has_data': True,
            'total_switches': len(switches),
            'switch_list': switches[:10],
            'common_patterns': most_common
        }
    
    def _analyze_categories(self) -> dict:
        """类别效率分析 - 基于合并后的真实工作段"""
        from collections import defaultdict
        
        cat_data = defaultdict(lambda: {'scores': [], 'minutes': 0, 'sessions': 0})
        
        for session in self.merged_sessions:
            cat = session['category'] or _('其他')
            if session['avg_score'] > 0:
                cat_data[cat]['scores'].append(session['avg_score'])
            cat_data[cat]['minutes'] += session['duration']
            cat_data[cat]['sessions'] += 1
        
        if not cat_data:
            return {'has_data': False}
        
        # 计算每个类别的统计
        cat_stats = {}
        for cat, data in cat_data.items():
            avg_score = int(sum(data['scores'])/len(data['scores'])) if data['scores'] else 0
            cat_stats[cat] = {
                'avg_score': avg_score,
                'total_mins': int(data['minutes']),
                'session_count': data['sessions'],  # 真实工作段数量
                'score_variance': self._calc_variance(data['scores']) if len(data['scores']) > 1 else 0
            }
        
        # 找最高效和最低效
        scored_cats = {k: v for k, v in cat_stats.items() if v['avg_score'] > 0}
        best_cat = max(scored_cats, key=lambda x: scored_cats[x]['avg_score']) if scored_cats else None
        worst_cat = min(scored_cats, key=lambda x: scored_cats[x]['avg_score']) if scored_cats else None
        
        return {
            'has_data': True,
            'stats': cat_stats,
            'best': best_cat,
            'worst': worst_cat
        }
    
    def _calc_variance(self, scores: list) -> int:
        """计算分数波动（标准差）"""
        if len(scores) < 2:
            return 0
        avg = sum(scores) / len(scores)
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)
        return int(variance ** 0.5)
    
    def _analyze_timeline(self) -> list:
        """生成时间线摘要 - 基于合并后的真实工作段"""
        timeline = []
        for session in self.merged_sessions[:15]:  # 最多15个工作段
            if session['start_time']:
                timeline.append({
                    'time': session['start_time'].strftime('%H:%M'),
                    'category': session['category'],
                    'duration': int(session['duration']),
                    'score': session.get('avg_score', 0)
                })
        return timeline
    
    def _classify_day_type(self) -> dict:
        """基于数据判断今日类型"""
        focus = self._analyze_focus()
        switching = self._analyze_switching()
        
        if not focus.get('has_data'):
            return {'type': _('数据不足'), 'description': _('记录较少，无法分类')}
        
        deep_count = focus.get('deep_count', 0)
        fragment_percent = focus.get('fragment_percent', 0)
        switch_count = switching.get('total_switches', 0)
        
        # 基于数据的客观分类
        if deep_count >= 2 and fragment_percent < 30:
            return {'type': _('深度工作日'), 'indicators': _('{deep_count}次深度工作，碎片仅{fragment_percent}%').format(deep_count=deep_count, fragment_percent=fragment_percent)}
        elif switch_count >= 8:
            return {'type': _('多任务切换日'), 'indicators': _('切换{switch_count}次').format(switch_count=switch_count)}
        elif fragment_percent > 60:
            return {'type': _('碎片化日'), 'indicators': _('{fragment_percent}%为碎片时间').format(fragment_percent=fragment_percent)}
        elif deep_count == 0 and focus.get('avg_duration', 0) < 20:
            return {'type': _('轻量日'), 'indicators': _('平均每段{avg_duration}分钟').format(avg_duration=focus.get('avg_duration', 0))}
        else:
            return {'type': _('常规日'), 'indicators': _('节奏正常')}


class AICommentGenerator:
    """AI 点评生成器 - 基于深度数据"""
    
    # 朋友式点评 Prompt
    COMMENT_PROMPT = _("""你是用户的一个懂时间管理的朋友。下面是他今天的时间记录数据，请基于【客观数据】写一段点评。

【写作风格】
- 像发微信语音转文字那样自然，可以用口语化表达
- 开头别用"今天"，换个角度切入（比如从某个有趣的数据点开始）
- 别总结数据，而是说出数据背后有意思的发现
- 别给建议，除非数据明显指向某个问题

【禁止使用】
- "继续保持"、"加油"、"相信你"、"明天会更好" 等鸡汤
- "今天你..."、"从数据来看..." 等套路开头
- 过多 emoji（最多1个，放结尾）
- 任何形式的猜测（"可能是因为..."）

【今日数据】
日期：{date}
记录时长：{recorded_time}
综合效率：{score}分
时间分布：{categories}

【专注力数据】
{focus_data}

【工作节奏数据】
{rhythm_data}

【任务切换数据】
{switching_data}

【类别效率数据】
{category_data}

【今日类型】
{day_type}

【输出要求】
- 100-150字
- 直接输出，不要标题
- 说人话，别像 AI""")

    # 专业深度分析 Prompt
    ANALYSIS_PROMPT = _("""你是一位专业的时间管理与行为分析专家。请基于以下用户今日的活动数据，撰写一份专业的深度分析报告。

【数据说明】
- "工作段"是指连续做同一类事情的时间段（系统自动识别并合并）
- 切换次数是指在不同类别之间切换的次数
- 效率分数基于屏幕活动的专注程度评估

【今日原始数据】
日期：{date}
总记录时长：{recorded_time}
综合效率评分：{score}分
今日类型：{day_type}
时间分布：{categories}

【专注力指标】
{focus_data}

【时段效率数据】
{rhythm_data}

【任务切换数据】
{switching_data}

【类别效率对比】
{category_data}

【分析要求】
请从以下维度进行深度分析，输出专业报告：

1. **行为模式诊断**
   - 今日的工作模式属于什么类型？（深度工作型/碎片化/多任务切换型）
   - 这种模式的利弊是什么？

2. **效率瓶颈识别**
   - 基于数据，找出今日效率的主要瓶颈点
   - 哪些时段或行为拖累了整体效率？

3. **优势与亮点**
   - 今日做得好的方面（用数据支撑）
   - 可以继续保持的良好习惯

4. **改进策略**（具体可执行）
   - 基于今日数据，给出2-3条针对性的改进建议
   - 建议要具体、可量化、可操作

【输出格式】
- 使用专业、客观的语言
- 分析要有数据支撑，避免空泛
- 总字数300-500字
- 使用 Markdown 格式，包含小标题
- 直接输出分析内容，不要有任何前言""")

    def __init__(self, storage=None):
        self.storage = storage
        self.api_base_url = config.API_BASE_URL.rstrip("/")
        self.model = config.API_MODEL
    
    def _get_api_key(self) -> str:
        """获取 API Key（优先从数据库读取）"""
        if self.storage:
            db_key = self.storage.get_setting("api_key", "")
            if db_key:
                return db_key
        return config.API_KEY
    
    def generate_comment(self, stats: dict, deep_analysis: dict) -> str:
        """
        生成 AI 点评
        
        Args:
            stats: 基础统计数据
            deep_analysis: DeepAnalyzer 生成的深度分析结果
        """
        api_key = self._get_api_key()
        if not api_key:
            return self._fallback_comment(stats, deep_analysis)
        
        try:
            recorded_h = stats['recorded_minutes'] // 60
            recorded_m = stats['recorded_minutes'] % 60
            
            categories_str = "、".join([
                f"{cat}({m//60}h{m%60}m)" 
                for cat, m in stats['categories'][:5]
            ]) if stats['categories'] else _("无记录")
            
            # 格式化深度分析数据
            focus = deep_analysis.get('focus', {})
            rhythm = deep_analysis.get('rhythm', {})
            switching = deep_analysis.get('switching', {})
            categories = deep_analysis.get('categories', {})
            day_type = deep_analysis.get('day_type', {})
            
            # 专注力数据
            if focus.get('has_data'):
                focus_data = _("""- 总共 {total_sessions} 段工作
- 碎片(<15分钟): {fragment_count}段，占{fragment_percen}%
- 深度工作(>60分钟): {deep_count}段，共{deep_total_mins}分钟
- 最长一段: {max_session_duration}分钟（{max_session_category}，{max_session_time}）
- 平均每段: {avg_duration}分钟""").format(
                        total_sessions=focus['total_sessions'],
                        fragment_count=focus['fragment_count'], 
                        fragment_percent=focus['fragment_percent'],
                        deep_count=focus['deep_count'],
                        deep_total_mins=focus['deep_total_mins'],
                        max_session_duration=focus['max_session']['duration'],
                        max_session_category=focus['max_session']['category'],
                        max_session_time=focus['max_session']['time'],
                        avg_duration=focus['avg_duration']
)
            else:
                focus_data = _("数据不足")
            
            # 节奏数据
            if rhythm.get('has_data'):
                period_lines = [_("- {name}: 均分{avg_score}，共{total_mins}分钟").format(
                                    name=name,
                                    avg_score=data['avg_score'],
                                    total_mins=data['total_mins'],
                                )
                               for name, data in rhythm.get('periods', {}).items()]
                rhythm_data = "\n".join(period_lines) if period_lines else _("数据不足")
                rhythm_data += _("\n- 效率最高时段: {peak_hour}点（{peak_score}分）").format(
                                    peak_hour=rhythm['peak_hour'],
                                    peak_score=rhythm['peak_score']
                                )
                rhythm_data += _("\n- 效率最低时段: {low_hour}点（{low_score}分）").format(
                                    low_hour=rhythm['low_hour'],
                                    low_score=rhythm['low_score']
                                )
            else:
                rhythm_data = _("数据不足")
            
            # 切换数据
            if switching.get('has_data'):
                switching_data = _("- 总切换次数: {total_switches}次").format(total_switches=switching['total_switches'])
                if switching.get('common_patterns'):
                    patterns = [f"{p[0]}({p[1]}次)" for p in switching['common_patterns']]
                    switching_data += _("\n- 常见切换: {patterns}").format(patterns=', '.join(patterns))
            else:
                switching_data = _("切换较少或无数据")
            
            # 类别数据
            if categories.get('has_data'):
                cat_lines = []
                for cat, data in categories.get('stats', {}).items():
                    cat_lines.append(_("- {cat}: 均分{avg_score}，{session_count}段共{total_mins}分钟").format(
                                        cat=cat,
                                        avg_score=data['avg_score'],
                                        session_count=data['session_count'],
                                        total_mins=data['total_mins']
                                     ))
                category_data = "\n".join(cat_lines[:5])
                if categories.get('best') and categories.get('worst') and categories['best'] != categories['worst']:
                    category_data += _("\n- 效率最高: {best}，最低: {worst}").format(
                        best=categories['best'],
                        worst=categories['worst'],
                    )
            else:
                category_data = _("数据不足")
            
            # 今日类型
            day_type_str = f"{day_type.get('type', _('常规日'))}（{day_type.get('indicators', '')}）"
            
            prompt = self.COMMENT_PROMPT.format(
                date=stats['date'],
                recorded_time=_("{recorded_h}小时{recorded_m}分钟").format(
                    recorded_h=recorded_h,
                    recorded_m=recorded_m
                ),
                score=stats['score'],
                categories=categories_str,
                focus_data=focus_data,
                rhythm_data=rhythm_data,
                switching_data=switching_data,
                category_data=category_data,
                day_type=day_type_str
            )
            
            comment = self._call_api_sync(prompt, api_key, max_tokens=200)
            return comment if comment else self._fallback_comment(stats, deep_analysis)
            
        except Exception as e:
            logger.error(f"AI 点评生成失败: {e}")
            return self._fallback_comment(stats, deep_analysis)
    
    def generate_deep_analysis(self, stats: dict, deep_analysis: dict) -> str:
        """
        生成专业深度分析报告
        
        Args:
            stats: 基础统计数据
            deep_analysis: DeepAnalyzer 生成的深度分析结果
        
        Returns:
            Markdown 格式的专业分析报告
        """
        api_key = self._get_api_key()
        if not api_key:
            return self._fallback_analysis(deep_analysis)
        
        try:
            recorded_h = stats['recorded_minutes'] // 60
            recorded_m = stats['recorded_minutes'] % 60
            
            categories_str = "、".join([
                f"{cat}({m//60}h{m%60}m)" 
                for cat, m in stats['categories'][:5]
            ]) if stats['categories'] else _("无记录")
            
            # 格式化深度分析数据
            focus = deep_analysis.get('focus', {})
            rhythm = deep_analysis.get('rhythm', {})
            switching = deep_analysis.get('switching', {})
            categories = deep_analysis.get('categories', {})
            day_type = deep_analysis.get('day_type', {})
            
            # 专注力数据
            if focus.get('has_data'):
                focus_data = _("""- 工作段数量: {total_sessions}段
- 碎片工作(<15min): {fragment_count}段，占比{fragment_percent}%
- 深度工作(>60min): {deep_count}段，累计{deep_total_mins}分钟
- 最长单次专注: {max_session_duration}分钟（{max_session_category}，{max_session_time}开始）
- 平均工作段时长: {avg_duration}分钟""").format(
                        total_sessions=focus['total_sessions'],
                        fragment_count=focus['fragment_count'],
                        fragment_percent=focus['fragment_percent'],
                        deep_count=focus['deep_count'],
                        deep_total_mins=focus['deep_total_mins'],
                        max_session_duration=focus['max_session']['duration'],
                        max_session_category=focus['max_session']['category'],
                        max_session_time=focus['max_session']['time'],
                        avg_duration=focus['avg_duration']
                )
            else:
                focus_data = _("数据不足，无法分析")
            
            # 节奏数据
            if rhythm.get('has_data'):
                period_lines = [_("- {name}: 效率均分{avg_score}分，工作{total_mins}分钟，{session_count}个工作段").format(
                                    name=name,
                                    avg_score=data['avg_score'],
                                    total_mins=data['total_mins'],
                                    session_count=data['session_count']
                                )
                               for name, data in rhythm.get('periods', {}).items()]
                rhythm_data = "\n".join(period_lines) if period_lines else _("数据不足")
                rhythm_data += f"\n- {_("效率峰值: {peak_hour}:00（{peak_score}分").format(peak_hour=rhythm['peak_hour'], peak_score=rhythm['peak_score'])}）"
                rhythm_data += f"\n- {_("效率低谷: {low_hour}:00（{low_score}分").format(low_hour=rhythm['low_hour'], low_score=rhythm['low_score'])}）"
                rhythm_data += f"\n- {_("峰谷差值: {score}分").format(score=rhythm['peak_score'] - rhythm['low_score'])}"
            else:
                rhythm_data = _("数据不足，无法分析")
            
            # 切换数据
            if switching.get('has_data'):
                switching_data = f"- {_("类别切换总次数")}: {switching['total_switches']}次"
                if switching.get('common_patterns'):
                    patterns = [_("{p0}（{p1}次）".format(p0=p[0], p1=[1])) for p in switching['common_patterns']]
                    switching_data += f"\n- {_("高频切换模式")}: {', '.join(patterns)}"
            else:
                switching_data = _("切换极少或无数据")
            
            # 类别数据
            if categories.get('has_data'):
                cat_lines = []
                for cat, data in sorted(categories.get('stats', {}).items(), 
                                        key=lambda x: x[1]['total_mins'], reverse=True):
                    variance_text = f"，{_("波动±{score_variance}").format(score_variance=data['score_variance'])}" if data['score_variance'] > 0 else ""
                    cat_lines.append(f"- {cat}: {_("效率{avg_score}分{variance_text}，{session_count}段共{total_mins}分钟").format(
                                avg_score=data['avg_score'],
                                variance_text=variance_text,
                                session_count=data['session_count'],
                                total_mins=data['total_mins']
                        )}")
                category_data = "\n".join(cat_lines[:6])
                if categories.get('best') and categories.get('worst') and categories['best'] != categories['worst']:
                    best_data = categories['stats'].get(categories['best'], {})
                    worst_data = categories['stats'].get(categories['worst'], {})
                    diff = best_data.get('avg_score', 0) - worst_data.get('avg_score', 0)
                    category_data += f"\n- {_("效率最高: {best}（{avg_score}分）").format(best=categories['best'], avg_score=best_data.get('avg_score', 0))}"
                    category_data += f"\n- {_("效率最低: {worst}（{avg_score}分）").format(worst=categories['worst'], avg_score=worst_data.get('avg_score', 0))}"
                    category_data += f"\n- {_("类别效率差: {diff}分").format(diff=diff)}"
            else:
                category_data = _("数据不足，无法分析")
            
            # 今日类型
            day_type_str = f"{day_type.get('type', _('常规日'))}（{day_type.get('indicators', '')}）"
            
            prompt = self.ANALYSIS_PROMPT.format(
                date=stats['date'],
                recorded_time=_("{recorded_h}小时{recorded_m}分钟").format(recorded_h=recorded_h, recorded_m=recorded_m),
                score=stats['score'],
                categories=categories_str,
                focus_data=focus_data,
                rhythm_data=rhythm_data,
                switching_data=switching_data,
                category_data=category_data,
                day_type=day_type_str
            )
            
            analysis = self._call_api_sync(prompt, api_key, max_tokens=1500)
            return analysis if analysis else self._fallback_analysis(deep_analysis)
            
        except Exception as e:
            logger.error(f"深度分析生成失败: {e}")
            return self._fallback_analysis(deep_analysis)
    
    def _fallback_analysis(self, deep_analysis: dict) -> str:
        """深度分析降级方案"""
        focus = deep_analysis.get('focus', {})
        rhythm = deep_analysis.get('rhythm', {})
        switching = deep_analysis.get('switching', {})
        day_type = deep_analysis.get('day_type', {})
        
        lines = [f"### {_('行为模式')}"]
        
        dtype = day_type.get('type', _('常规日'))
        lines.append(f"{_('今日属于')} **{dtype}**。{day_type.get('indicators', '')}")
        
        if focus.get('has_data'):
            lines.append("")
            lines.append(f"### {_("专注力表现")}")
            if focus.get('deep_count', 0) > 0:
                lines.append(f"- {_("完成了 {deep_count} 次深度工作（>60分钟），累计 {deep_total_mins} 分钟").format(deep_count=focus['deep_count'], deep_total_mins=focus['deep_total_mins'])}")
            lines.append(f"- {_("最长专注 {duration} 分钟").format(duration=focus.get('max_session', {}).get('duration', 0))}")
            lines.append(f"- {_("碎片工作占比 {fragment_percent}%")}".format(fragment_percent=focus.get('fragment_percent', 0)))
        
        if rhythm.get('has_data'):
            lines.append("")
            lines.append(f"### {_("时段效率")}")
            lines.append(f"- {_("效率峰值在 {peak_hour}:00（{peak_score}分）").format(peak_hour=rhythm.get('peak_hour', 0), peak_score=rhythm.get('peak_score', 0))}")
            lines.append(f"- {_("效率低谷在 {low_hour}:00（{low_score}分）").format(low_hour=rhythm.get('low_hour', 0), low_score=rhythm.get('low_score', 0))}")
        
        if switching.get('has_data') and switching.get('total_switches', 0) > 0:
            lines.append("")
            lines.append(f"### {_("任务切换")}")
            lines.append(f"- 今日切换 {switching['total_switches']} 次")
        
        return "\n".join(lines)
    
    def _call_api_sync(self, prompt: str, api_key: str, max_tokens: int = 300) -> Optional[str]:
        """同步调用 API"""
        try:
            # 长输出需要更长超时
            timeout = 30.0 if max_tokens > 500 else 15.0
            
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.api_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": max_tokens  # 使用传入的参数
                    }
                )
                response.raise_for_status()
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return content.strip() if content else None
        except httpx.HTTPStatusError as e:
            logger.warning(f"API HTTP 错误: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.warning(f"API 请求错误: {e}")
            return None
        except Exception as e:
            logger.warning(f"API 调用失败: {type(e).__name__}: {e}")
            return None
    
    def _fallback_comment(self, stats: dict, deep_analysis: dict) -> str:
        """降级方案：基于深度分析数据生成点评"""
        score = stats['score']
        recorded_h = stats['recorded_minutes'] // 60
        categories = stats.get('categories', [])
        focus = deep_analysis.get('focus', {})
        day_type = deep_analysis.get('day_type', {})
        
        parts = []
        
        # 基于今日类型
        dtype = day_type.get('type', '')
        if dtype == _('深度工作日'):
            parts.append(_("今天是个深度工作日，{deep_count}段超过60分钟的专注时间").format(deep_count=focus.get('deep_count', 0)))
        elif dtype == _('碎片化日'):
            parts.append(_("今天时间比较碎片化，{fragment_percent}%是短时间片段").format(fragment_percent=focus.get('fragment_percent', 0)))
        elif dtype == _('多任务切换日'):
            parts.append(_("今天切换了不少任务类型，上下文切换成本不小"))
        else:
            if score >= 70:
                parts.append(_("今天{recorded_h}小时的工作，综合效率{score}分，节奏不错").format(recorded_h=recorded_h, score=score))
            else:
                top_cat = categories[0][0] if categories else _("工作")
                parts.append(_("今天主要在「{top_cat}」上花了时间").format(top_cat=top_cat))
        
        # 加一个数据亮点
        if focus.get('has_data') and focus.get('max_session'):
            ms = focus['max_session']
            parts.append(_("最长的一段是{duration}分钟的{category}（{time}开始）").format(duration=ms['duration'], category=ms['category'], time=ms['time']))        
        return "。".join(parts) + " ✨"


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, storage):
        self.storage = storage
        self.ai_generator = AICommentGenerator(storage)
    
    def generate_daily_report(self, date: datetime = None) -> str:
        """生成每日报告 HTML"""
        if date is None:
            date = datetime.now()
        
        # 获取当天数据
        cards = self.storage.get_cards_for_date(date)
        
        # 统计各类别时间
        category_stats = {}
        total_minutes = 0
        
        for card in cards:
            category = card.category or _("其他")
            minutes = card.duration_minutes
            category_stats[category] = category_stats.get(category, 0) + minutes
            total_minutes += minutes
        
        # 排序
        sorted_stats = sorted(category_stats.items(), key=lambda x: x[1], reverse=True)
        
        # 计算效率评分
        total_score = 0
        score_count = 0
        for card in cards:
            if card.productivity_score > 0:
                total_score += card.productivity_score
                score_count += 1
        avg_score = int(total_score / score_count) if score_count > 0 else 0
        
        # 深度分析
        analyzer = DeepAnalyzer(cards)
        deep_analysis = analyzer.analyze()
        
        # 构建 AI 使用的统计数据
        ai_stats = {
            'date': date.strftime(_("%Y年%m月%d日")),
            'recorded_minutes': int(total_minutes),
            'score': avg_score,
            'categories': [(cat, int(mins)) for cat, mins in sorted_stats]
        }
        
        # 生成 AI 点评（朋友式）
        try:
            ai_comment = self.ai_generator.generate_comment(ai_stats, deep_analysis)
        except Exception as e:
            logger.warning(f"AI 点评生成失败: {e}")
            ai_comment = _("今天的数据已记录完成 ✨")
        
        # 生成专业深度分析报告
        try:
            expert_analysis = self.ai_generator.generate_deep_analysis(ai_stats, deep_analysis)
        except Exception as e:
            logger.warning(f"专业分析生成失败: {e}")
            expert_analysis = ""
        
        # 生成 HTML（包含深度分析）
        return self._build_html(date, sorted_stats, total_minutes, avg_score, deep_analysis, ai_comment, expert_analysis)
    
    def _build_html(self, date: datetime, stats: list, 
                    total_minutes: int, score: int, deep_analysis: dict, 
                    ai_comment: str, expert_analysis: str = "") -> str:
        """构建 HTML 邮件内容（含深度分析和专业报告）"""
        date_str = date.strftime(_("%Y年%m月%d日"))
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)
        
        # 类别颜色
        category_colors = {
            _("工作"): "#4F46E5", "Work": "#4F46E5",
            _("学习"): "#059669", "Study": "#059669",
            _("编程"): "#6366F1", "Programming": "#6366F1",
            _("娱乐"): "#DC2626", "Entertainment": "#DC2626",
            _("休息"): "#F59E0B", "Rest": "#F59E0B",
            _("社交"): "#EC4899", "Social": "#EC4899",
            _("其他"): "#78716C", "Other": "#78716C",
        }
        
        # 构建时间分布条
        stats_html = ""
        for category, minutes in stats[:6]:  # 最多显示6个
            color = category_colors.get(category, "#78716C")
            percent = (minutes / total_minutes * 100) if total_minutes > 0 else 0
            h, m = int(minutes // 60), int(minutes % 60)
            bar_width = min(percent, 100)
            
            stats_html += f"""
            <div style="margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                    <span style="font-weight: 500; color: #374151; font-size: 13px;">{category}</span>
                    <span style="color: #6B7280; font-size: 12px;">{h}h {m}m ({percent:.0f}%)</span>
                </div>
                <div style="background-color: #E5E7EB; border-radius: 4px; height: 6px; overflow: hidden;">
                    <div style="background-color: {color}; width: {bar_width}%; height: 100%;"></div>
                </div>
            </div>"""
        
        # 效率评价
        if score >= 80:
            score_emoji, score_text, score_color = "🌟", _("非常高效"), "#059669"
        elif score >= 60:
            score_emoji, score_text, score_color = "👍", _("表现不错"), "#4F46E5"
        elif score >= 40:
            score_emoji, score_text, score_color = "💪", _("稳步前进"), "#F59E0B"
        else:
            score_emoji, score_text, score_color = "🎯", _("明天更好"), "#6B7280"
        
        # 提取深度分析数据
        focus = deep_analysis.get('focus', {})
        rhythm = deep_analysis.get('rhythm', {})
        switching = deep_analysis.get('switching', {})
        categories = deep_analysis.get('categories', {})
        day_type = deep_analysis.get('day_type', {})
        
        # 构建深度分析 HTML
        deep_html = self._build_deep_analysis_html(focus, rhythm, switching, categories, day_type)
        
        # 完整 HTML
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #F3F4F6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;">
    <div style="max-width: 640px; margin: 0 auto; padding: 20px;">
        <!-- 头部 -->
        <div style="background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); border-radius: 16px 16px 0 0; padding: 24px; text-align: center;">
            <h1 style="margin: 0; color: white; font-size: 22px; font-weight: 600;">📊 Dayflow {_('深度分析报告')}</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">{date_str}</p>
            <div style="margin-top: 12px; display: inline-block; background: rgba(255,255,255,0.2); padding: 6px 16px; border-radius: 20px;">
                <span style="color: white; font-size: 13px;">{day_type.get('type', '常规日')}</span>
            </div>
        </div>
        
        <!-- 主体 -->
        <div style="background-color: white; padding: 24px; border-radius: 0 0 16px 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            
            <!-- 总览卡片 -->
            <div style="display: flex; gap: 12px; margin-bottom: 20px;">
                <div style="flex: 1; background-color: #F0F9FF; border-radius: 10px; padding: 14px; text-align: center;">
                    <div style="font-size: 24px; font-weight: 700; color: #0369A1;">{hours}h {mins}m</div>
                    <div style="color: #6B7280; font-size: 12px; margin-top: 2px;">{_('记录时长')}</div>
                </div>
                <div style="flex: 1; background-color: #F0FDF4; border-radius: 10px; padding: 14px; text-align: center;">
                    <div style="font-size: 24px; font-weight: 700; color: {score_color};">{score_emoji} {score}</div>
                    <div style="color: #6B7280; font-size: 12px; margin-top: 2px;">{score_text}</div>
                </div>
                <div style="flex: 1; background-color: #FEF3C7; border-radius: 10px; padding: 14px; text-align: center;">
                    <div style="font-size: 24px; font-weight: 700; color: #D97706;">{focus.get('deep_count', 0)}</div>
                    <div style="color: #6B7280; font-size: 12px; margin-top: 2px;">{_('深度工作')}</div>
                </div>
            </div>
            
            <!-- 时间分布 -->
            <div style="margin-bottom: 20px;">
                <h2 style="font-size: 15px; font-weight: 600; color: #111827; margin: 0 0 12px 0;">
                    {_('📈 时间分布')}
                </h2>
                {stats_html if stats_html else f'<div style="color: #9CA3AF; text-align: center; padding: 20px;">{_("暂无数据")}</div>'}
            </div>
            
            <!-- 分隔线 -->
            <div style="border-top: 1px solid #E5E7EB; margin: 20px 0;"></div>
            
            <!-- 深度分析 -->
            <div style="margin-bottom: 20px;">
                <h2 style="font-size: 15px; font-weight: 600; color: #111827; margin: 0 0 16px 0;">
                    {_('🔍 深度分析')}
                </h2>
                {deep_html}
            </div>
            
            <!-- 分隔线 -->
            <div style="border-top: 1px solid #E5E7EB; margin: 20px 0;"></div>
            
            <!-- AI 点评 -->
            <div style="background: linear-gradient(135deg, #EDE9FE 0%, #DDD6FE 100%); border-radius: 12px; padding: 16px;">
                <h2 style="font-size: 15px; font-weight: 600; color: #5B21B6; margin: 0 0 10px 0;">
                    {_('💬 今日洞察')}
                </h2>
                <p style="margin: 0; color: #4C1D95; font-size: 14px; line-height: 1.8;">
                    {ai_comment}
                </p>
            </div>
            
            {self._build_expert_analysis_html(expert_analysis) if expert_analysis else ''}
        </div>
        
        <!-- 页脚 -->
        <div style="text-align: center; padding: 16px; color: #9CA3AF; font-size: 11px;">
            {_('由 Dayflow 自动生成')} · {datetime.now().strftime("%H:%M")}
        </div>
    </div>
</body>
</html>"""
        
        return html
    
    def _build_deep_analysis_html(self, focus: dict, rhythm: dict, 
                                   switching: dict, categories: dict, day_type: dict) -> str:
        """构建深度分析部分的 HTML"""
        sections = []
        
        # 1. 专注力分析
        if focus.get('has_data'):
            max_s = focus.get('max_session', {})
            focus_html = f"""
            <div style="background: #F8FAFC; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                <div style="font-weight: 600; color: #334155; font-size: 13px; margin-bottom: 10px;">{_('🎯 专注力数据')}</div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <div style="background: white; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; flex: 1; min-width: 120px;">
                        <div style="font-size: 18px; font-weight: 600; color: #0F172A;">{_('{duration}分钟').format(duration=focus.get('max_session', {}).get('duration', 0))}</div>
                        <div style="font-size: 11px; color: #64748B;">{_('最长专注')}</div>
                    </div>
                    <div style="background: white; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; flex: 1; min-width: 120px;">
                        <div style="font-size: 18px; font-weight: 600; color: #0F172A;">{_('{deep_total_mins}分钟').format(deep_total_mins=focus.get('deep_total_mins', 0))}</div>
                        <div style="font-size: 11px; color: #64748B;">{_('深度工作(>60min)')}</div>
                    </div>
                    <div style="background: white; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; flex: 1; min-width: 120px;">
                        <div style="font-size: 18px; font-weight: 600; color: {'#DC2626' if focus.get('fragment_percent', 0) > 50 else '#0F172A'};">{focus.get('fragment_percent', 0)}%</div>
                        <div style="font-size: 11px; color: #64748B;">{_('碎片占比(<15min)')}</div>
                    </div>
                </div>
                <div style="margin-top: 10px; font-size: 12px; color: #64748B;">
                    {_("共 {total_sessions} 段工作 · 平均每段 {avg_duration} 分钟 · 最长: {category} ({time})").format(total_sessions=focus.get('total_sessions', 0), avg_duration=focus.get('avg_duration', 0))}
                    {_("").format(category=max_s.get('category', ''), time=max_s.get('time', '')) if max_s.get('category') else ''}
                </div>
            </div>"""
            sections.append(focus_html)
        
        # 2. 工作节奏分析
        if rhythm.get('has_data'):
            periods = rhythm.get('periods', {})
            rhythm_bars = ""
            max_score = max([p.get('avg_score', 0) for p in periods.values()]) if periods else 100
            
            for name, data in periods.items():
                score = data.get('avg_score', 0)
                bar_width = (score / max_score * 100) if max_score > 0 else 0
                is_peak = (rhythm.get('peak_hour', -1) >= 6 and rhythm.get('peak_hour', -1) < 12 and _('上午') in name) or \
                         (rhythm.get('peak_hour', -1) >= 12 and rhythm.get('peak_hour', -1) < 18 and _('下午') in name) or \
                         (rhythm.get('peak_hour', -1) >= 18 and '晚上' in name)
                
                rhythm_bars += f"""
                <div style="margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                        <span style="font-size: 12px; color: #374151;">{name.split('(')[0]} {'⭐' if is_peak else ''}</span>
                        <span style="font-size: 12px; color: #6B7280;">{_('{score}分 · {total_mins}分钟').format(score=score, total_mins=data.get('total_mins', 0))}</span>
                    </div>
                    <div style="background: #E5E7EB; border-radius: 3px; height: 8px;">
                        <div style="background: {'#10B981' if score >= 70 else '#F59E0B' if score >= 50 else '#EF4444'}; width: {bar_width}%; height: 100%; border-radius: 3px;"></div>
                    </div>
                </div>"""
            
            rhythm_html = f"""
            <div style="background: #F8FAFC; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                <div style="font-weight: 600; color: #334155; font-size: 13px; margin-bottom: 10px;">{_('⏰ 时段效率')}</div>
                {rhythm_bars}
                <div style="margin-top: 8px; font-size: 12px; color: #64748B;">
                    {('效率峰值: {peak_hour}:00 ({peak_score}分) · 低谷: {low_hour}:00 ({low_score}分)').format(
                        peak_hour=rhythm.get('peak_hour', ''),
                        peak_score=rhythm.get('peak_score', 0),
                        low_hour=rhythm.get('low_hour', ''),
                        low_score=rhythm.get('low_score', 0),
                    )}
                </div>
            </div>"""
            sections.append(rhythm_html)
        
        # 3. 任务切换分析
        if switching.get('has_data') and switching.get('total_switches', 0) > 0:
            switch_count = switching.get('total_switches', 0)
            switch_color = '#10B981' if switch_count <= 3 else '#F59E0B' if switch_count <= 6 else '#EF4444'
            switch_text = _('非常聚焦') if switch_count <= 3 else _('节奏正常') if switch_count <= 6 else _('切换频繁')
            
            patterns = switching.get('common_patterns', [])
            pattern_str = " · ".join([f"{p[0]}" for p in patterns[:2]]) if patterns else ""
            
            switch_html = f"""
            <div style="background: #F8FAFC; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                <div style="font-weight: 600; color: #334155; font-size: 13px; margin-bottom: 10px;">{_('🔄 任务切换')}</div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="background: {switch_color}; color: white; font-size: 20px; font-weight: 700; padding: 12px 20px; border-radius: 8px;">
                        {switch_count}
                    </div>
                    <div>
                        <div style="font-size: 14px; font-weight: 500; color: #0F172A;">{switch_text}</div>
                        <div style="font-size: 12px; color: #64748B;">{_('今日类别切换次数')}</div>
                    </div>
                </div>
                {f'<div style="margin-top: 8px; font-size: 12px; color: #64748B;">{_('常见切换:')} {pattern_str}</div>' if pattern_str else ''}
            </div>"""
            sections.append(switch_html)
        
        # 4. 类别效率对比
        if categories.get('has_data') and len(categories.get('stats', {})) >= 2:
            cat_stats = categories.get('stats', {})
            best = categories.get('best')
            worst = categories.get('worst')
            
            if best and worst and best != worst:
                best_data = cat_stats.get(best, {})
                worst_data = cat_stats.get(worst, {})
                
                cat_html = f"""
                <div style="background: #F8FAFC; border-radius: 10px; padding: 14px;">
                    <div style="font-weight: 600; color: #334155; font-size: 13px; margin-bottom: 10px;">{_('📊 类别效率对比')}</div>
                    <div style="display: flex; gap: 10px;">
                        <div style="flex: 1; background: #DCFCE7; border-radius: 8px; padding: 10px; text-align: center;">
                            <div style="font-size: 11px; color: #166534;">{_('效率最高')}</div>
                            <div style="font-size: 15px; font-weight: 600; color: #15803D; margin: 4px 0;">{best}</div>
                            <div style="font-size: 18px; font-weight: 700; color: #166534;">{_('{avg_score}分').format(avg_score=best_data.get('avg_score', 0))}</div>
                            <div style="font-size: 11px; color: #166534;">
                                {_('{session_count}段 · {total_mins}分钟').format(
                                    session_count=best_data.get('session_count', 0),
                                    total_mins=best_data.get('total_mins', 0),
                                )}
                            </div>
                        </div>
                        <div style="flex: 1; background: #FEF3C7; border-radius: 8px; padding: 10px; text-align: center;">
                            <div style="font-size: 11px; color: #92400E;">{_('效率较低')}</div>
                            <div style="font-size: 15px; font-weight: 600; color: #B45309; margin: 4px 0;">{worst}</div>
                            <div style="font-size: 18px; font-weight: 700; color: #92400E;">{_('{avg_score}分').format(avg_score=worst_data.get('avg_score', 0))}</div>
                            <div style="font-size: 11px; color: #92400E;">{worst_data.get('session_count', 0)}段 · {worst_data.get('total_mins', 0)}分钟</div>
                        </div>
                    </div>
                </div>"""
                sections.append(cat_html)
        
        return "\n".join(sections) if sections else f'<div style="color: #9CA3AF; text-align: center; padding: 20px;">{_('数据量较少，暂无深度分析')}</div>'
    
    def _build_expert_analysis_html(self, expert_analysis: str) -> str:
        """构建专业分析报告的 HTML"""
        import re
        
        # 将 Markdown 转换为 HTML
        html_content = expert_analysis
        
        # 转换 Markdown 标题
        html_content = re.sub(r'^### (.+)$', r'<h4 style="font-size: 14px; font-weight: 600; color: #1E3A5F; margin: 16px 0 8px 0;">\1</h4>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^## (.+)$', r'<h3 style="font-size: 15px; font-weight: 600; color: #1E3A5F; margin: 16px 0 10px 0;">\1</h3>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content, flags=re.MULTILINE)
        
        # 转换粗体
        html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
        
        # 转换列表项
        html_content = re.sub(r'^- (.+)$', r'<div style="margin: 4px 0; padding-left: 12px;">• \1</div>', html_content, flags=re.MULTILINE)
        
        # 转换换行
        html_content = html_content.replace('\n\n', '</p><p style="margin: 8px 0; color: #334155; font-size: 13px; line-height: 1.7;">')
        html_content = html_content.replace('\n', '<br>')
        
        return f"""
            <!-- 分隔线 -->
            <div style="border-top: 1px solid #E5E7EB; margin: 24px 0;"></div>
            
            <!-- 专业深度分析报告 -->
            <div style="background: linear-gradient(135deg, #E0F2FE 0%, #BAE6FD 100%); border-radius: 12px; padding: 20px; margin-top: 16px;">
                <h2 style="font-size: 16px; font-weight: 600; color: #0C4A6E; margin: 0 0 16px 0; display: flex; align-items: center;">
                    {_('📋 专业分析报告')}
                </h2>
                <div style="background: white; border-radius: 8px; padding: 16px; color: #334155; font-size: 13px; line-height: 1.7;">
                    <p style="margin: 0; color: #334155; font-size: 13px; line-height: 1.7;">
                        {html_content}
                    </p>
                </div>
            </div>"""


class EmailScheduler:
    """
    邮件定时调度器 - 增强版
    
    功能:
    - 支持可配置的发送时间
    - 持久化发送记录到数据库
    - 应用启动时检查错过的报告
    - 系统唤醒时重新检查
    - 带指数退避的重试机制
    - 发送失败时托盘通知
    """
    
    # 错过报告的补发窗口（小时）
    CATCH_UP_WINDOW_HOURS = 2
    
    # 重试配置
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 60  # 秒
    
    def __init__(
        self, 
        email_service: EmailService, 
        report_generator: ReportGenerator,
        storage=None,
        config_manager=None,
        tray_icon=None
    ):
        """
        初始化邮件调度器
        
        Args:
            email_service: 邮件服务实例
            report_generator: 报告生成器实例
            storage: StorageManager 实例（用于持久化发送记录）
            config_manager: ConfigManager 实例（用于获取可配置发送时间）
            tray_icon: 系统托盘图标（用于发送通知）
        """
        self.email_service = email_service
        self.report_generator = report_generator
        self.storage = storage
        self.config_manager = config_manager
        self.tray_icon = tray_icon
        
        # 内存缓存（兼容旧逻辑）
        self._last_noon_send: Optional[datetime] = None
        self._last_night_send: Optional[datetime] = None
    
    def on_app_start(self) -> None:
        """
        应用启动时检查错过的报告
        
        如果上次发送时间超过 24 小时但在补发窗口内，则补发
        """
        logger.info("检查是否有错过的邮件报告...")
        
        send_times = self._get_send_times()
        now = datetime.now()
        
        for hour, minute in send_times:
            period = f"{hour:02d}:{minute:02d}"
            last_send = self._get_last_send_time(period)
            
            if last_send is None:
                continue
            
            # 计算今天的预定发送时间
            scheduled_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # 如果预定时间在未来，检查昨天的
            if scheduled_today > now:
                scheduled_today -= timedelta(days=1)
            
            # 检查是否错过（上次发送在预定时间之前，且在补发窗口内）
            if last_send < scheduled_today:
                time_since_scheduled = (now - scheduled_today).total_seconds() / 3600
                if time_since_scheduled <= self.CATCH_UP_WINDOW_HOURS:
                    logger.info(f"检测到错过的报告 ({period})，正在补发...")
                    self._send_report(period)
    
    def on_system_wake(self) -> None:
        """
        系统从睡眠唤醒时调用
        
        重新检查是否有错过的报告
        """
        logger.info("系统唤醒，重新检查邮件报告...")
        self.on_app_start()
    
    def check_and_send(self):
        """检查是否需要发送报告（每分钟调用一次）"""
        now = datetime.now()
        today = now.date()
        
        send_times = self._get_send_times()
        
        for hour, minute in send_times:
            # 检查是否在发送窗口内（10 分钟容错）
            if now.hour == hour and now.minute < 10:
                period = f"{hour:02d}:{minute:02d}"
                last_send = self._get_last_send_time(period)
                
                # 检查今天是否已发送
                if last_send is None or last_send.date() != today:
                    logger.info(f"触发 {period} 邮件发送")
                    self._send_report(period)
        
        # 兼容旧逻辑（硬编码时间）
        if not send_times or send_times == [(12, 0), (22, 0)]:
            # 中午 12:00-12:10 时间窗口
            if now.hour == 12 and now.minute < 10:
                if self._last_noon_send is None or self._last_noon_send.date() != today:
                    logger.info("触发午间邮件发送")
                    self._send_report("noon")
                    self._last_noon_send = now
            
            # 晚上 22:00-22:10 时间窗口
            if now.hour == 22 and now.minute < 10:
                if self._last_night_send is None or self._last_night_send.date() != today:
                    logger.info("触发晚间邮件发送")
                    self._send_report("night")
                    self._last_night_send = now
    
    def _get_send_times(self) -> List[Tuple[int, int]]:
        """获取配置的发送时间列表"""
        if self.config_manager:
            return self.config_manager.get_email_send_times()
        return [(12, 0), (22, 0)]  # 默认值
    
    def _send_report(self, period: str):
        """发送报告（带重试）"""
        success = self._send_with_retry(period)
        
        if not success:
            # 发送托盘通知
            self._notify_failure(period)
    
    def _send_with_retry(self, period: str) -> bool:
        """
        带指数退避重试的发送逻辑
        
        Args:
            period: 时间段标识
        
        Returns:
            是否发送成功
        """
        now = datetime.now()
        date_str = now.strftime(_("%m月%d日"))
        
        # 构建邮件主题
        if period == "noon":
            subject = _("📊 Dayflow 午间报告 - {date_str}").format(date_str=date_str)
        elif period == "night":
            subject = _("📊 Dayflow 晚间报告 - {date_str}").format(date_str=date_str)
        else:
            subject = _("📊 Dayflow {period} 报告 - {date_str}").format(period=period, date_str=date_str)
        
        last_error = ""
        
        for attempt in range(self.MAX_RETRIES):
            try:
                html = self.report_generator.generate_daily_report(now)
                success, error_msg = self.email_service.send_report(subject, html)
                
                if success:
                    logger.info(f"定时报告发送成功: {period} (尝试 {attempt + 1})")
                    self._save_last_send_time(period, now, success=True, retry_count=attempt)
                    return True
                else:
                    last_error = error_msg
                    logger.warning(f"发送失败 (尝试 {attempt + 1}/{self.MAX_RETRIES}): {error_msg}")
            
            except Exception as e:
                last_error = str(e)
                logger.error(f"发送异常 (尝试 {attempt + 1}/{self.MAX_RETRIES}): {e}")
            
            # 指数退避等待
            if attempt < self.MAX_RETRIES - 1:
                delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                logger.info(f"等待 {delay} 秒后重试...")
                import time
                time.sleep(delay)
        
        # 所有重试都失败
        logger.error(f"定时报告发送失败（已重试 {self.MAX_RETRIES} 次）: {period}")
        self._save_last_send_time(period, now, success=False, error_message=last_error, retry_count=self.MAX_RETRIES)
        return False
    
    def _get_last_send_time(self, period: str) -> Optional[datetime]:
        """从数据库获取上次成功发送时间"""
        if not self.storage:
            # 兼容模式：使用内存缓存
            if period == "noon":
                return self._last_noon_send
            elif period == "night":
                return self._last_night_send
            return None
        
        try:
            # 使用独立连接查询
            import sqlite3
            conn = sqlite3.connect(str(self.storage.db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT send_time FROM email_send_log 
                WHERE period = ? AND success = 1 
                ORDER BY send_time DESC LIMIT 1
                """,
                (period,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return datetime.fromisoformat(row["send_time"])
            return None
        
        except Exception as e:
            logger.warning(f"获取上次发送时间失败: {e}")
            return None
    
    def _save_last_send_time(
        self, 
        period: str, 
        send_time: datetime, 
        success: bool = True,
        error_message: str = "",
        retry_count: int = 0
    ) -> None:
        """保存发送记录到数据库"""
        # 更新内存缓存
        if period == "noon":
            self._last_noon_send = send_time
        elif period == "night":
            self._last_night_send = send_time
        
        if not self.storage:
            return
        
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.storage.db_path), timeout=10.0)
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(
                """
                INSERT INTO email_send_log (period, send_time, success, error_message, retry_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (period, send_time.isoformat(), 1 if success else 0, error_message, retry_count)
            )
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            logger.debug(f"已保存发送记录: {period} at {send_time}")
        
        except Exception as e:
            logger.error(f"保存发送记录失败: {e}")
    
    def _notify_failure(self, period: str) -> None:
        """发送失败时显示托盘通知"""
        if self.tray_icon:
            try:
                self.tray_icon.showMessage(
                    _("Dayflow 邮件发送失败"),
                    _("{period} 报告发送失败，请检查网络和邮箱配置").format(period=period),
                    self.tray_icon.MessageIcon.Warning,
                    5000
                )
            except Exception as e:
                logger.warning(f"显示托盘通知失败: {e}")
    
    def send_test_email(self) -> tuple:
        """发送测试邮件，返回 (成功, 错误信息)"""
        try:
            now = datetime.now()
            subject = _("🧪 Dayflow 测试邮件 - {now}").format(now=now.strftime('%H:%M'))
            html = self.report_generator.generate_daily_report(now)
            return self.email_service.send_report(subject, html)
        except Exception as e:
            logger.error(f"发送测试邮件失败: {e}")
            return False, str(e)
