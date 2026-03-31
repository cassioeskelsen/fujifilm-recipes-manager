from django.core.management.base import BaseCommand

from src.application.usecases.images import process_images


class Command(BaseCommand):
    help = "Enqueue a Celery task for every JPG image found in the given folder."

    def add_arguments(self, parser):
        parser.add_argument("folder", type=str, help="Path to the folder containing images.")

    def handle(self, *args, **options):
        folder = options["folder"]
        self.stdout.write(f"Scanning {folder} for JPG files…")

        total = process_images.enqueue_images_in_folder(folder=folder)

        self.stdout.write(self.style.SUCCESS(f"Successfully enqueued {total} tasks."))
