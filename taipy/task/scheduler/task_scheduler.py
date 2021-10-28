__all__ = ["TaskScheduler"]

import logging
import uuid
from multiprocessing import Lock
from queue import Queue
from typing import Callable, Dict, Iterable, List, Optional

from taipy.config import Config
from taipy.exceptions import JobNotDeletedException, NonExistingJob
from taipy.task import Task

from ...config.task_scheduler import TaskSchedulerConfig
from .executor.executor import Executor
from .job import Job, JobId


class TaskScheduler:
    """
    Create and schedule Jobs from Task and keep their states
    """

    def __init__(self, task_scheduler_config: TaskSchedulerConfig = Config.task_scheduler_configs.create()):
        self.__JOBS: Dict[JobId, Job] = {}
        self.jobs_to_run: Queue[Job] = Queue()
        self.__executor = Executor(
            task_scheduler_config.parallel_execution, task_scheduler_config.max_number_of_parallel_execution
        )
        self.lock = Lock()

    def submit(self, task: Task, callbacks: Optional[Iterable[Callable]] = None) -> Job:
        """
        Submit a task that should be executed as a Job

        The result of the Task executed is provided to its output data source
        by mapping each element with each output data source of the Task.
        If the number of output data sources is
        different to the number of Task results, we do nothing

        If an error happens when the result is provided to a data source, we ignore it
        and continue to the next data source
        """
        job = self.__create_job(task, callbacks or [])
        self.jobs_to_run.put(job)
        job.pending()
        self.__run()
        return job

    def get_job(self, job_id: JobId) -> Job:
        try:
            return self.__JOBS[job_id]
        except KeyError:
            logging.error(f"Job : {job_id} does not exist.")
            raise NonExistingJob(job_id)

    def get_jobs(self) -> List[Job]:
        return list(self.__JOBS.values())

    def delete(self, job: Job):
        if job.is_finished():
            del self.__JOBS[job.id]
        else:
            err = JobNotDeletedException(job.id)
            logging.warning(err)
            raise err

    def get_latest_job(self, task: Task) -> Job:
        return max(filter(lambda job: task in job, self.__JOBS.values()))

    def __run(self):
        with self.lock:
            self.__execute_jobs()

    def __execute_jobs(self):
        while not self.jobs_to_run.empty() and self.__executor.can_execute():
            job_to_run = self.jobs_to_run.get()
            self.__executor.execute(job_to_run)

    def __job_finished(self, job: Job):
        if job.is_finished():
            if self.lock.acquire(block=False):
                try:
                    self.__execute_jobs()
                except:
                    ...
                finally:
                    self.lock.release()

    def __create_job(self, task: Task, callbacks: Iterable[Callable]) -> Job:
        job = Job(id=JobId(f"job_id_{task.id}_{uuid.uuid4()}"), task=task)
        self.__JOBS[job.id] = job
        job.on_status_change(self.__job_finished, *callbacks)
        return job
