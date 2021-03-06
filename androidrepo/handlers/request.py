# This file is part of AndroidRepo (Telegram Bot)
# Copyright (C) 2021 AmanoTeam

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import time
from typing import List

from pyrogram import Client, filters
from pyrogram.types import Message, User

from androidrepo.config import STAFF_ID, SUDO_USERS
from androidrepo.database import Requests


@Client.on_message(
    filters.private & (filters.cmd("request ") | filters.regex("^#request "))
)
async def on_request_m(c: Client, m: Message):
    user = m.from_user
    requests = await Requests.filter(user=user.id)
    last_request = None

    last_request_time = 0
    if requests:
        last_request = requests[-1]
        last_request_time = last_request.time

    now_time = time.time()

    if user.id not in SUDO_USERS:
        now = datetime.datetime.fromtimestamp(now_time)
        if last_request_time > 0:
            last = datetime.datetime.fromtimestamp(last_request_time)
            if last_request.attempts > 3:
                if bool(last_request.ignore):
                    return
                last_request.update_from_dict({"ignore": 1})
                await last_request.save()
                await c.send_log_message(
                    f"{user.mention} was spamming requests and has been ignored."
                )
                return await m.reply_text(
                    "You have spammed too many requests, so you will be ignored."
                )
            if (now - last).seconds < (3 * 60):
                last_request.update_from_dict({"attempts": (last_request.attempts) + 1})
                await last_request.save()
                await c.send_log_message(f"{user.mention} is spamming requests.")
                return await m.reply_text(
                    "You cannot send multiple requests one after the other, wait 3 minutes."
                )

    if len(requests) > 15:
        return await m.reply_text("You have reached the requests limit.")

    request = m.text[len(m.text.split()[0]) + 1 :]
    sent = await c.send_log_message(
        f"""
<b>New request</b>:
    <b>From</b>: {user.mention}
    <b>Request</b>: {request}
    """
    )
    if sent:
        await Requests.create(
            user=user.id,
            time=now_time,
            ignore=0,
            request=request,
            attempts=0,
            request_id=(last_request.request_id if last_request else 0) + 1,
            message_id=sent.message_id,
        )
        await m.reply_text("Your request was successfully sent!")
    else:
        await m.reply_text("There was a problem submitting your request.")


@Client.on_message(filters.private & filters.cmd("myrequests"))
async def on_myrequests_m(c: Client, m: Message):
    user = m.from_user
    requests = await Requests.filter(user=user.id)

    if len(requests) > 0:
        text = f"<b>Ignored</b>: <code>{bool(requests[-1].ignore)}</code>\n\n"
        text += "<b>Requests</b>:\n"
        for request in requests:
            text += f"    {request.request_id}: <code>{request.request}</code>\n"
        text += "\nUse <code>/cancelrequest &lt;id&gt;</code> to cancel a request."
        return await m.reply_text(text)
    return await m.reply_text("You haven't sent any request yet.")


@Client.on_message(filters.private & filters.cmd(r"cancelrequest (?P<id>\d+)"))
async def on_cancelrequest_m(c: Client, m: Message):
    id = m.matches[0]["id"]
    user = m.from_user
    request = await Requests.filter(user=user.id, request_id=id).first()

    await c.delete_log_messages(message_ids=request.message_id)

    if request:
        await request.delete()
        return await m.reply_text("Request canceled successfully!")
    return await m.reply_text("Request not found.")


@Client.on_message((filters.chat(STAFF_ID) | filters.sudo) & filters.cmd("ignore"))
async def on_ignore_m(c: Client, m: Message):
    reply = m.reply_to_message
    if reply:
        user = reply.from_user
    else:
        text_splited = m.text.split()
        if len(text_splited) > 1:
            user = text_splited[1]
        return await m.reply_text("Specify someone.")

    if not isinstance(user, User):
        try:
            user = await c.get_users(user)
        except BaseException:
            return await m.reply_text("This user was not found.")

    if user.id in SUDO_USERS:
        return

    requests = await Requests.filter(user=user.id)
    if requests:
        last_request = requests[-1]
    else:
        await Requests.create(
            user=user.id, time=time.time(), ignore=1, request="", attempts=0
        )
        return await m.reply_text(f"{user.mention} can't send requests.")

    if not bool(last_request.ignore):
        last_request.update_from_dict({"ignore": 1})
        await last_request.save()
        return await m.reply_text(f"{user.mention} can't send requests.")
    return await m.reply_text(f"{user.mention} is already ignored.")


@Client.on_message((filters.chat(STAFF_ID) | filters.sudo) & filters.cmd("unignore"))
async def on_unignore_m(c: Client, m: Message):
    reply = m.reply_to_message
    if reply:
        user = reply.from_user
    else:
        text_splited = m.text.split()
        if len(text_splited) > 1:
            user = text_splited[1]
        return await m.reply_text("Specify someone.")

    if not isinstance(user, User):
        try:
            user = await c.get_users(user)
        except BaseException:
            return await m.reply_text("This user was not found.")

    if user.id in SUDO_USERS:
        return

    requests = await Requests.filter(user=user.id)
    if requests:
        last_request = requests[-1]
    else:
        return await m.reply_text(f"{user.mention} is not ignored.")

    if bool(last_request.ignore):
        last_request.update_from_dict({"attempts": 0, "ignore": 0})
        await last_request.save()
        return await m.reply_text(f"{user.mention} can send requests again.")
    return await m.reply_text(f"{user.mention} is not ignored.")


@Client.on_message(filters.chat(STAFF_ID) & filters.cmd("done") & filters.reply)
async def on_done_m(c: Client, m: Message):
    query = m.text.split()
    command = query[0]
    reply = m.reply_to_message
    request = await Requests.filter(message_id=reply.message_id)
    if len(request) > 0:
        request = request[0]
        user_id = request.user
        request_id = request.request_id
        await c.send_message(
            chat_id=user_id,
            text=f"""
<b>Request done</b>:
    <b>ID</b>: <code>{request_id}</code>
    <b>Don't be surprised, it will disappear from your request list.</b>
    {("<b>Staff message</b>: <code>" + m.text[len(command)+1:] + "</code>") if len(query) > 1 else ""}
    <b>Request</b>: <code>{request.request}</code>
        """,
        )
        await request.delete()
        await m.reply_text("The request was successfully done.")


@Client.on_message(
    filters.chat(STAFF_ID) & filters.reply & filters.regex("^(?P<answer>.+)")
)
async def on_reply_m(c: Client, m: Message):
    answer = m.matches[0]["answer"]
    reply = m.reply_to_message
    request = await Requests.filter(message_id=reply.message_id)
    if len(request) > 0:
        request = request[0]
        user_id = request.user
        request_id = request.request_id
        await c.send_message(
            chat_id=user_id,
            text=f"""
<b>Answer to your request</b>:
    <b>ID</b>: <code>{request_id}</code>
    <b>Answer</b>: <code>{answer}</code>
        """,
        )
    else:
        m.continue_propagation()


@Client.on_deleted_messages(filters.chat(STAFF_ID))
async def on_deleted_m(c: Client, messages: List[Message]):
    for m in messages:
        request = await Requests.filter(message_id=m.message_id)
        if len(request) > 0:
            request = request[0]
            user_id = request.user
            request_id = request.request_id
            await c.send_message(
                chat_id=user_id,
                text=f"""
<b>Request canceled</b>:
    <b>ID</b>: <code>{request_id}</code>
    <b>Request</b>: <code>{request.request}</code>
            """,
            )
            await request.delete()
