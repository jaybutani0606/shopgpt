from django.core.management.base import BaseCommand
from analytics.loaders import load_results_df, clean_df
from analytics.models import AnalyticsSnapshot

class Command(BaseCommand):
    help = 'Loads all ProductResults, runs analytics pipeline, and stores snapshot.'

    def handle(self, *args, **options):
        df = load_results_df()
        clean = clean_df(df)
        snapshot = AnalyticsSnapshot.create_from(clean)
        self.stdout.write(self.style.SUCCESS(f'Successfully created analytics snapshot ID {snapshot.id}'))
