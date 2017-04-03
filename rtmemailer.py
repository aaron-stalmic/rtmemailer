import feedparser
from datetime import datetime
import dateutil.parser
import re
from driver_emails import *
import urllib
import urllib.request
from itertools import filterfalse
from feed_url import feed_url
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import threading


def parse(feed):
    """
    Parses an XML feed from feedparser and converts it to a dict of dicts
    containing important information.
    """
    tasks = {}
    for item in feed['items']:
        _id = item['id']
        task = {}
        # Grab the title, date, and link.
        task['title'] = item['title']
        task['date'] = dateutil.parser.parse(item['date'])
        task['link'] = item['link']
        # Tags, due dates, and priorities are in the content section and must
        # be regex'd.
        content = item['content']
        match = re.search('tags_value">([^<]*)', item['content'][0]['value'])
        if match:
            task['tags'] = match.group(1).split(', ')
        match = re.search('due_value">([^<]*)', item['content'][0]['value'])
        if match:
            task['due_date'] = dateutil.parser.parse(match.group(1))
        match = re.search('priority_value">([^<]*)', item['content'][0]['value'])
        if match:
            p = match.group(1)
            # Priorities are either an integer or 'none'.
            if p == 'none':
                task['priority'] = 0
            else:
                task['priority'] = int(p)
        tasks[_id] = task
    return tasks


def diff_check(live_feed, local_feed):
    """
    Checks for a difference between two parsed feeds and returns a list of
    differing tasks.
    """
    diff = []
    for task in live_feed.keys():
        if task not in local_feed.keys():
            diff.append(live_feed[task])
    return diff


def create_text(task, person):
    """
    Creates a plain text version of an E-mail.
    """
    name = person[0]
    title = task['title'].upper()
    # Only include time if it is not midnight.
    due_date = datetime.strftime(task['due_date'], '%a %b %e, %Y').replace('  ', ' ')
    if task['due_date'].hour != 0:
        due_date += ' @ '
        due_date += datetime.strftime(task['due_date'], '%I:%M %p').lstrip('0')
    priority = task['priority']
    tags = ', '.join(task['tags'])
    link = task['link']
    text = """{}, you have a new task on Remember the Milk:

{}
Due: {}
Priority: {}
Tags: {}

You can view more information at:
{}
or by using your Remember the Milk app.
""".format(name, title, due_date, priority, tags, link)
    return text


def create_html(task, person):
    """
    Creates an HTML version of an E-mail.
    """
    name = person[0]
    title = task['title']
    due_date = datetime.strftime(task['due_date'], '%a %b %e, %Y').replace('  ', ' ')
    if task['due_date'].hour != 0:
        due_date += ' @ '
        due_date += datetime.strftime(task['due_date'], '%I:%M %p').lstrip('0')
    priority = task['priority']
    tags = ', '.join(task['tags'])
    link = task['link']
    html = """\
    <html>
    <head></head>
    <body>
    <p><b>{0}, you have a new task on Remember the Milk:</b></p><br/>
    <h2 style="margin-left: 20pt"><a href="{5}">{1}</a></h2>
    <p style="margin-left: 20pt"><b>Due:</b> {2}<br/>
    <b>Priority:</b> {3}<br/>
    <b>Tags:</b> {4}</p><br/>
    <p>You can view more information at: <br/>
    <a href="{5}">{5}</a> <br/>
    or by using your Remember the Milk app.</p>
    </body>
    </html>
    """.format(name, title, due_date, priority, tags, link)
    return html


def send_email(task, person):
    """
    Takes a task and a person list containing a name and E-mail and sends the
    formated task the the E-mail.
    """
    from_adr = from_email
    to_adr = person[1]
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "You have a new task."
    msg['From'] = from_adr
    msg['To'] = to_adr
    to_adr = [to_adr]
    # Steve also wants a copy.
    if (person[1] != steve_email) and (person[0] != 'Drivers'):
        msg['CC'] = steve_email
        to_adr.append(steve_email)
    text = create_text(task, person)
    html = create_html(task, person)
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')
    msg.attach(part1)
    msg.attach(part2)
    server = smtplib.SMTP('secure.emailsrvr.com', 587)
    server.ehlo()
    server.starttls()
    server.login(username, password)
    server.sendmail(from_adr, to_adr, msg.as_string())
    print("Sending E-mails to {} for job {}.".format(', '.join(to_adr), task['link'][-8:]))
    server.quit()


def check():
    """
    Checks the online feed against a local copy every 10 minutes.
    """
    threading.Timer(600, check).start()
    local_feed = feedparser.parse('feed.xml')
    # If a feed is not formatted correctly, feedparser sets 'bozo' as 1.
    if local_feed['bozo'] == 1:
        urllib.request.urlretrieve(feed_url, 'feed.xml')
        local_feed = feedparser.parse('feed.xml')
    local_feed = parse(local_feed)
    live_feed = feedparser.parse(feed_url)
    live_feed = parse(live_feed)
    diff = diff_check(live_feed, local_feed)
    for task in diff:
        for tag in task['tags']:
            if tag in emails.keys():
                send_email(task, emails[tag])
    # If there are differences, download the new feed.
    if len(diff) > 0:
        urllib.request.urlretrieve(feed_url, 'feed.xml')

if __name__ == '__main__':
    print("Now monitoring live feed.")
    check()
