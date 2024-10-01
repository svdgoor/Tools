import os
import argparse
import logging
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EXTS = ["png", "jpg", "webp"]

file_counts = {EXT: 0 for EXT in EXTS + ["other", "did-not-exist", "error"]}
created_counts = {EXT: 0 for EXT in EXTS}

progress = {
    "total_files": 0,
    "processed_files": 0
}


def convert(image: str):
    try:
        im = Image.open(image)
        img_without_ext = (".".join(image.split(".")[:-1]))
        logger.debug(f"Converting {image}")
        conv = im.convert("RGB")
        for ext in EXTS:
            if image.endswith(f".{ext}"):
                for other_ext in EXTS:
                    if ext != other_ext and not \
                            os.path.exists(f"{img_without_ext}.{other_ext}"):
                        logger.debug(f"Creating {img_without_ext}.{other_ext}")
                        conv.save(
                            f"{img_without_ext}.{other_ext}",
                            other_ext if other_ext != "jpg" else "jpeg"
                        )
                        created_counts[other_ext] += 1
                break
    except Exception as e:
        logger.error(f"Error converting {image}: {e}")
        file_counts["error"] += 1


def report_progress():
    start_time = time.time()
    last_time = start_time
    while progress["processed_files"] < progress["total_files"]:
        if time.time() - last_time > 1:
            last_time = time.time()
            percent_complete = \
                (progress["processed_files"] * 100) / progress["total_files"]
            eta = ((time.time() - start_time) / percent_complete) * \
                (100 - percent_complete) if percent_complete > 0 else 0
            logger.info(
                f"Conversion progress: {percent_complete:.2f}% "
                f"({progress['processed_files']}/"
                f"{progress['total_files']})"
                f" - Elapsed time: {time.time() - start_time:.2f}s"
                f" - ETA: {eta:.2f}s"
            )
        time.sleep(0.01)


def convert_all(path: str, recursive: bool, workers: int = 4):
    logger.info("Starting conversion process...")
    files = []
    if recursive:
        for root, _, filenames in os.walk(path):
            for file in filenames:
                files.append(os.path.join(root, file))
    else:
        files = [os.path.join(path, file) for file in os.listdir(path)]

    progress["total_files"] = len(files)
    logger.info(f"Total files found: {progress['total_files']}")

    progress_thread = threading.Thread(target=report_progress)
    progress_thread.start()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for file in files:
            if not os.path.isfile(file):
                file_counts["did-not-exist"] += 1
                progress["total_files"] -= 1
            elif file.split(".")[-1] not in EXTS:
                file_counts["other"] += 1
                progress["total_files"] -= 1
            else:
                futures[executor.submit(convert, file)] = file

        for future in as_completed(futures):
            file = futures[future]
            try:
                future.result()
                if file.split(".")[-1] in EXTS:
                    file_counts[file.split(".")[-1]] += 1
                else:
                    file_counts["other"] += 1
            except Exception as e:
                logger.error(f"Error processing file {file}: {e}")
            progress["processed_files"] += 1

    progress_thread.join()

    logger.info("Conversion process finished.")
    logger.info(f"Files found: {file_counts}")
    logger.info(f"Files created: {created_counts}")


def convert_single(image: str):
    logger.info("Starting conversion process...")
    convert(image)
    logger.info("Conversion process finished.")
    logger.info(f"Files found: {file_counts}")
    logger.info(f"Files created: {created_counts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Converts images to other formats")
    parser.add_argument("path", help="Path to convert")
    parser.add_argument(
        "--directory",
        action="store_true",
        help="Convert all images in a directory"
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively convert images in subdirectories"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print verbose output"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of workers to use for conversion"
    )
    args = parser.parse_args()
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    logger.debug(args)
    if not args.directory and not args.recursive:
        if not os.path.isfile(args.path):
            logger.error("Invalid path provided")
            logger.error("If you want to specify a folder, use --directory")
        else:
            convert_single(args.path)
    else:
        if not os.path.exists(args.path):
            logger.error("Invalid path provided")
        else:
            convert_all(args.path, args.recursive, args.workers)
