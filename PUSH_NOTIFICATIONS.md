# Mobile push notifications

New cars and expenses notify active administrators, the car owner, and the
assigned driver on every device they have enabled. Creation through the app
and Django admin is covered. Editing an existing entry does not send another
notification. Notifications show the car and action; amounts, receipts, and
phone numbers are not put on the lock screen.

## Server setup

Install `requirements.txt` and apply migrations:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
```

Generate a key pair once, using your actual HTTPS website as the contact:

```powershell
.\.venv\Scripts\python.exe manage.py generate_push_keys --subject https://axiocar.up.railway.app --configure-local
```

The command writes `.run/push-keys.env` and adds the settings to local `.env`.
Both are ignored by Git and Docker. It refuses to overwrite existing keys.
Keep the pair stable: changing it requires devices to subscribe again.

For Railway, copy the three values from `.run/push-keys.env` to the **web service**
Variables and deploy the updated source:

- `PUSH_VAPID_PUBLIC_KEY`
- `PUSH_VAPID_PRIVATE_KEY`
- `PUSH_VAPID_SUBJECT`

Use the Dockerfile's default start command. `deploy/start.py` starts one push
worker alongside Gunicorn, restarts it if it exits, and stops it when the web
service stops. No extra Railway service or Redis instance is required.
The pre-deploy migration step creates the subscription and delivery tables.

For local development, restart the web server after adding keys and run the
worker in another terminal:

```powershell
.\.venv\Scripts\python.exe manage.py send_push_notifications --loop
```

Without `--loop`, the command processes the currently due jobs and exits.

## Enable each phone

1. Open the HTTPS website, install AutoLedger, and sign in.
2. Go to **Profile → Mobile notifications → Enable notifications**.
3. Allow notifications in the phone/browser prompt.

On iPhone/iPad, use iOS/iPadOS 16.4 or later. Add AutoLedger to the Home Screen
and launch it from that icon before enabling notifications. Android browsers
with Web Push support can also receive notifications while the app is closed.
The phone's notification permissions, connectivity, and Focus settings still
control presentation. Desktop browsers with Web Push are supported too.

Each browser installation has its own subscription. A user can disable just
the current device from Profile. Signing out detaches the current session's
device to protect shared phones. Signing in with another account rebinds that
device to the new account when its existing subscription is registered.

## Delivery and verification

Jobs are stored in PostgreSQL after the record transaction commits. The worker
checks current car access before sending and retries temporary failures up to
five attempts. Expired subscriptions are removed. A crashed worker's claimed
jobs become eligible after two minutes; OS notification tags group retries of
the same event. Browser push services can hold accepted notifications for up
to one hour while a phone is offline. Final delivery depends on the platform.

Test with two real accounts/devices: enable notifications for an admin and an
assigned driver, add a car/expense, then tap each notification to open its car
or expense history. Unassign a driver and verify they no longer receive future
updates for that car. Automated tests mock delivery to avoid sending messages
to real devices.

References: [WebKit: iPhone/iPad Home Screen Web Push](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/),
[MDN: Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API),
[pywebpush](https://github.com/web-push-libs/pywebpush).
