#!/bin/env python

import argparse
import datetime
import requests
import os
from utils import ip_address, config_file
from packtpub import Packtpub
from upload import Upload, SERVICE_DRIVE, SERVICE_DROPBOX, SERVICE_SCP
from database import Database, DB_FIREBASE
from logs import *
from notify import Notify, SERVICE_GMAIL, SERVICE_IFTTT, SERVICE_JOIN
from noBookException import NoBookException

def parse_types(args):
    if args.types is None:
        return [args.type]
    else:
        return args.types

def handleClaim(packtpub, args, config, dir_path):
    if args.dev:
        log_json(packtpub.info)

    log_success('[+] book successfully claimed')

    upload = None
    upload_info = None

    if not args.claimOnly:
        types = parse_types(args)

        packtpub.download_ebooks(types, dir_path)

        if args.extras:
            packtpub.download_extras(dir_path)

        if args.archive:
            raise NotImplementedError('not implemented yet!')

        if args.upload is not None:
            upload = Upload(config, args.upload)
            upload.run(packtpub.info['paths'])

        if upload is not None and upload is not SERVICE_DRIVE:
            log_warn('[-] skip store info: missing upload info')
        elif args.store is not None:
            Database(config, args.store, packtpub.info, upload.info).store()

    if args.notify:
        if upload is not None:
            upload_info = upload.info

        Notify(config, packtpub.info, upload_info, args.notify).run()

def main():
    parser = argparse.ArgumentParser(
        description='Download FREE eBook every day from www.packtpub.com',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        version='2.2.0')

    parser.add_argument('-c', '--config', required=True, help='configuration file')
    parser.add_argument('-d', '--dev', action='store_true', help='only for development')
    parser.add_argument('-e', '--extras', action='store_true', help='download source code (if exists) and book cover')
    parser.add_argument('-u', '--upload', choices=[SERVICE_DRIVE, SERVICE_DROPBOX, SERVICE_SCP], help='upload to cloud')
    parser.add_argument('-a', '--archive', action='store_true', help='compress all file')
    parser.add_argument('-n', '--notify', choices=[SERVICE_GMAIL, SERVICE_IFTTT, SERVICE_JOIN], help='notify after claim/download')
    parser.add_argument('-s', '--store', choices=[DB_FIREBASE], help='store info')
    parser.add_argument('-o', '--claimOnly', action='store_true', help='only claim books (no downloads/uploads)')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-t', '--type', choices=['pdf', 'epub', 'mobi'],
        default='pdf', help='specify eBook type')
    group.add_argument('--all', dest='types', action='store_const',
        const=['pdf', 'epub', 'mobi'], help='all eBook types')

    args = parser.parse_args()

    now = datetime.datetime.now()
    log_info('[*] {date} - Fetching today\'s ebook'.format(date=now.strftime("%Y-%m-%d %H:%M")))

    packtpub = None

    try:
        dir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.path.sep

        config = config_file(dir_path + args.config)
        packtpub = Packtpub(config, args.dev)

        #ip_address()
        log_info('[*] getting daily free ebook')

        try:
            packtpub.runDaily()
            handleClaim(packtpub, args, config, dir_path)
        except NoBookException as e:
            log_info('[*] ' + e.message)
        except Exception as e:
            log_debug(e)
            if args.notify:
                Notify(config, None, None, args.notify).sendError(e, 'daily')
            return

        lastNewsletterUrlPath = dir_path + 'config/lastNewsletterUrl'
        lastNewsletterUrl = None

        if os.path.isfile(lastNewsletterUrlPath):
            with open(lastNewsletterUrlPath, 'r+') as f:
                lastNewsletterUrl = f.read().strip()

        # the default URL is generated by an Google apps script, see README for details and self-hosting
        currentNewsletterUrl = requests.get(config.get('url', 'url.bookFromNewsletter')).text.strip()

        if currentNewsletterUrl == '':
            log_info('[*] no free book from newsletter right now')
        elif not currentNewsletterUrl.startswith('http'):
            log_warn('[-] invalid URL from newsletter: ' + currentNewsletterUrl)
        elif lastNewsletterUrl != currentNewsletterUrl:
            log_info('[*] getting free ebook from newsletter')
            try:
                packtpub.runNewsletter(currentNewsletterUrl)
                handleClaim(packtpub, args, config, dir_path)

                with open(lastNewsletterUrlPath, 'w+') as f:
                    f.write(currentNewsletterUrl)

            except Exception as e:
                log_debug(e)
                if args.notify:
                    Notify(config, None, None, args.notify).sendError(e, 'newsletter')
        else:
            log_info('[*] already got latest ebook from newsletter, skipping')

    except KeyboardInterrupt:
        log_error('[-] interrupted manually')

    except Exception as e:
        log_debug(e)
        if args.notify:
            Notify(config, None, None, args.notify).sendError(e, 'global')

    log_info('[*] done')

if __name__ == '__main__':
    print ("""
                      __   __              __                                   __
    ____  ____ ______/ /__/ /_____  __  __/ /_        ______________ __      __/ /__  _____
   / __ \/ __ `/ ___/ //_/ __/ __ \/ / / / __ \______/ ___/ ___/ __ `/ | /| / / / _ \/ ___/
  / /_/ / /_/ / /__/ ,< / /_/ /_/ / /_/ / /_/ /_____/ /__/ /  / /_/ /| |/ |/ / /  __/ /
 / .___/\__,_/\___/_/|_|\__/ .___/\__,_/_.___/      \___/_/   \__,_/ |__/|__/_/\___/_/
/_/                       /_/

Download FREE eBook every day from www.packtpub.com
@see github.com/niqdev/packtpub-crawler
        """)
    main()
