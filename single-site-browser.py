#!/usr/bin/env python3

import argparse
import inspect
import os
import requests
import urllib
import shutil
import subprocess
import sys

from contextlib import suppress
from pathlib import Path

user_chrome_contents = inspect.cleandoc(
    """
    #nav-bar, #identity-box, #tabbrowser-tabs, #TabsToolbar {
        visibility: collapse !important;
    }
    """
)

user_js_contents = inspect.cleandoc(
    """
    user_pref("browser.cache.disk.enable", false);
    user_pref("browser.cache.disk.capacity", 0);
    user_pref("browser.cache.disk.filesystem_reported", 1);
    user_pref("browser.cache.disk.smart_size.enabled", false);
    user_pref("browser.cache.disk.smart_size.first_run", false);
    user_pref("browser.cache.disk.smart_size.use_old_max", false);
    user_pref("browser.ctrlTab.previews", true);
    user_pref("browser.tabs.warnOnClose", false);
    user_pref("plugin.state.flash", 2);
    user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
    """
)

desktop_file_contents = inspect.cleandoc(
    """
    [Desktop Entry]
    Version=1.0
    Name={name}
    Comment=Comment here
    GenericName=Generic Name here
    Keywords=Semicolon-separated keywords
    Exec={command}
    Terminal=false
    X-MultipleArgs=false
    Type=Application
    Icon={icon}
    Categories=Accessories
    MimeType=
    StartupNotify=true
    StartupWMClass={wm_class}
    """
)


class SsbFirefox:
    def __init__(self, url, name=None):
        self.url = url

        if name is None:
            self.name = (
                self.url.replace("http://", "")
                .replace("https://", "")
                .replace("/", "_")
            )
        else:
            self.name = name

    @property
    def config_path(self):
        return Path.home().joinpath(".local", "share", "ssb", self.name)

    @property
    def profile_path(self):
        return self.config_path / "profile"

    def generate_profile(self):
        user_chrome = self.profile_path.joinpath("chrome", "userChrome.css")
        if not user_chrome.exists():
            user_chrome.parent.mkdir(parents=True, exist_ok=True)
            with open(user_chrome, "w") as f:
                f.write(user_chrome_contents)

        user_js = self.profile_path.joinpath("user.js")
        if not user_js.exists():
            user_js.parent.mkdir(parents=True, exist_ok=True)
            with open(user_js, "w") as f:
                f.write(user_js_contents)

    def download_icon(self):
        favicon = self.favicon_path
        if not favicon.exists():
            favicon.parent.mkdir(parents=True, exist_ok=True)
            parsed = urllib.parse.urlparse(self.url)
            favicon_url = f"https://{parsed.hostname}/favicon.ico"
            res = requests.get(favicon_url)

            with open(favicon, "wb") as f:
                f.write(res.content)

    @property
    def command(self):
        return [
            "firefox",
            "-profile",
            self.profile_path,
            "-no-remote",
            "-new-instance",
            self.url,
            "--class",
            self.wm_class,
        ]

    @property
    def favicon_path(self):
        return self.config_path / "favicon.ico"

    @property
    def wm_class(self):
        return f"SSB_{self.name}"

    @property
    def desktop_file_symlink(self):
        return Path.home().joinpath(
            ".local", "share", "applications", f"{self.name}.desktop"
        )

    @property
    def desktop_file(self):
        return self.config_path / "application-menu-item.desktop"

    def generate_desktop_file(self):
        relpath = os.path.relpath(self.desktop_file, self.desktop_file_symlink.parent)
        if self.desktop_file_symlink.exists():
            # Don't overwrite an existing file, or an existing symlink
            # that points somewhere else.
            if self.desktop_file_symlink.resolve() != self.desktop_file:
                raise FileExistsError(self.desktop_file_symlink)
        else:
            os.symlink(relpath, self.desktop_file_symlink)

        self.generate_profile()
        self.download_icon()
        with open(self.desktop_file, "w") as f:
            f.write(
                desktop_file_contents.format(
                    name=self.name,
                    command=" ".join(str(s) for s in self.command),
                    icon=self.favicon_path,
                    wm_class=self.wm_class,
                )
            )

    def clean(self):
        with suppress(FileNotFoundError):
            shutil.rmtree(self.config_path)
        with suppress(FileNotFoundError):
            os.remove(self.desktop_file)

    def run(self):
        self.generate_profile()
        try:
            subprocess.check_call(self.command)
        finally:
            shutil.rmtree(self.profile_path.joinpath("cache2"))


def main(args):
    ssb = SsbFirefox(args.url, args.name)

    if args.mode == "application-menu":
        ssb.generate_desktop_file()
    elif args.mode == "run":
        ssb.run()
    elif args.mode == "clean":
        ssb.clean()
    else:
        raise ValueError(f'Unknown mode "{args.mode}"')


def normalize_url(url):
    if url.startswith("http"):
        return url
    else:
        return "https://" + url


def arg_main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["application-menu", "run", "clean"],
        default="application-menu",
        help=(
            "The action to be taken.  "
            '"application-menu" will generate a *.desktop menu item.  '
            '"run" will run the single-site browser without generating a menu item.  '
            '"clean" will remove any profile and desktop file.'
        ),
    )
    parser.add_argument(
        "-u",
        "--url",
        required=True,
        help="The URL for the single-site browser",
        type=normalize_url,
    )
    parser.add_argument(
        "-n", "--name", help="The unique name for the single-site browser"
    )
    parser.add_argument(
        "--pdb",
        action="store_true",
        help="Start a pdb post mortem on uncaught exception",
    )

    args = parser.parse_args()

    try:
        main(args)
    except Exception:
        if args.pdb:
            import pdb, traceback

            traceback.print_exc()
            pdb.post_mortem()
        raise


if __name__ == "__main__":
    arg_main()
