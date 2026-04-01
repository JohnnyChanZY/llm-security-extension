"""
定时任务调度服务
使用APScheduler实现定时数据采集和推送
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class SchedulerService:
    """定时任务调度服务"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False

    def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("调度器已在运行中")
            return

        # 添加定时任务
        self._add_jobs()

        # 启动调度器
        self.scheduler.start()
        self.is_running = True
        logger.info("定时任务调度器已启动")

    def stop(self):
        """停止调度器"""
        if not self.is_running:
            return

        self.scheduler.shutdown()
        self.is_running = False
        logger.info("定时任务调度器已停止")

    def _add_jobs(self):
        """添加定时任务"""
        # RSS爬取任务 - 每30分钟
        from .rss_crawler import crawl_all_sources
        self.scheduler.add_job(
            crawl_all_sources,
            IntervalTrigger(minutes=30),
            id="rss_crawler",
            name="RSS爬取",
            replace_existing=True
        )

        # 历史数据同步任务 - 每天凌晨3点
        from .historical_sync import sync_all_sources
        self.scheduler.add_job(
            sync_all_sources,
            CronTrigger(hour=3, minute=0),
            id="historical_sync",
            name="历史数据同步",
            replace_existing=True
        )

        # 事件推送任务 - 每1分钟
        from .event_pusher import push_pending_events
        self.scheduler.add_job(
            push_pending_events,
            IntervalTrigger(minutes=1),
            id="event_pusher",
            name="事件推送",
            replace_existing=True
        )

        # LLM自动评级任务 - 每5分钟
        from .llm_rating import auto_rate_events
        self.scheduler.add_job(
            auto_rate_events,
            IntervalTrigger(minutes=5),
            id="llm_rating",
            name="LLM自动评级",
            replace_existing=True
        )

        # 数据清理任务 - 每天凌晨4点
        from .data_cleanup import cleanup_old_data
        self.scheduler.add_job(
            cleanup_old_data,
            CronTrigger(hour=4, minute=0),
            id="data_cleanup",
            name="数据清理",
            replace_existing=True
        )

        logger.info("已添加所有定时任务")

    def run_job(self, job_id: str):
        """手动执行指定任务"""
        job = self.scheduler.get_job(job_id)
        if job:
            job.func()
            return True
        return False

    def run_all_jobs(self):
        """手动执行所有任务"""
        logger.info("手动执行所有任务...")
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            try:
                job.func()
            except Exception as e:
                logger.error(f"执行任务 {job.id} 失败: {e}")


# 创建默认实例
scheduler = SchedulerService()
