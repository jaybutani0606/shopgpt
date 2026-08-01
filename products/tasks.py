from celery import shared_task
from products.services import SearchService

@shared_task
def run_search_task(query, search_id):
    SearchService.run(query, search_id)
