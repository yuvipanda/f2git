import os
import asyncio
import argparse
import stat
from datetime import datetime
import pytz


async def canvas_fetch(canvas_url, canvas_key, course_id, destination):
    from canvasapi import Canvas

    canvas = Canvas(canvas_url, canvas_key)
    course = canvas.get_course(course_id)

    for folder in course.get_folders():
        for file in folder.get_files():
            dest_path = os.path.join(destination, folder.full_name, file.filename)
            if os.path.exists(dest_path):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(dest_path)).astimezone(pytz.utc)
                if file.updated_at_date <= file_mtime:
                    print(f'{dest_path} up to date, skipping')
                    continue
            # FIXME: protect against path traversal attacks here
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            file.download(dest_path)
            print(f'downloaded {dest_path}')


def parse_args():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        'bare_repos_dir',
        help='Directory to find bare repos in'
    )
    argparser.add_argument(
        'checkout_dir',
        help='Directory to store checked out repos in'
    )

    return argparser.parse_args()

async def main():
    args = parse_args()
    course_id = 1315638
    repo_path = os.path.abspath(os.path.join(args.bare_repos_dir, str(course_id)))
    checkout_path = os.path.abspath(os.path.join(args.checkout_dir, str(course_id)))

    if not os.path.exists(repo_path):
        await (await asyncio.create_subprocess_exec(*[
            'git', 'init', '--bare', repo_path
        ])).wait()
        # Make our bare repository serveable over dumb HTTP
        post_update_hook_path = os.path.join(repo_path, 'hooks', 'post-update')
        os.rename(
            os.path.join(repo_path, 'hooks', 'post-update.sample'),
            post_update_hook_path
        )
        os.chmod(post_update_hook_path, os.stat(post_update_hook_path).st_mode | stat.S_IEXEC)

    if not os.path.exists(checkout_path):
        await (await asyncio.create_subprocess_exec(*[
            'git', 'clone', repo_path, checkout_path
        ])).wait()

    while True:
        await canvas_fetch(
            'https://bcourses.berkeley.edu',
            os.environ['CANVAS_API_KEY'],
            course_id,
            checkout_path
        )

        await (await asyncio.create_subprocess_exec(*[
            'git', 'add', '.'
        ], cwd=checkout_path)).wait()

        await (await asyncio.create_subprocess_exec(*[
            'git', 'commit', '-m', 'test'
        ], cwd=checkout_path)).wait()

        await (await asyncio.create_subprocess_exec(*[
            'git', 'push', 'origin', 'master'
        ], cwd=checkout_path)).wait()

        await asyncio.sleep(1 * 60)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()