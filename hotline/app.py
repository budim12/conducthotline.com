# Copyright 2019 Alethea Katherine Flowers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import click
import flask
import flask_talisman
import jinja2
import phonenumbers

import hotline.auth.webhandlers
import hotline.csrf
import hotline.events.webhandlers
import hotline.numberadmin.webhandlers
import hotline.pages.webhandlers
import hotline.telephony.webhandlers

app = flask.Flask(__name__)
hotline.csrf.init_app(app)

flask_talisman.Talisman(
    app,
    content_security_policy={
        "default-src": ["'self'"],
        "script-src": [
            "'self'",
            "www.gstatic.com",
            "cdn.firebase.com",
            "apis.google.com",
            "use.fontawesome.com",
        ],
        "style-src": [
            "'self'",
            "fonts.googleapis.com",
            "cdn.firebase.com",
            "cdnjs.cloudflare.com",
            "use.fontawesome.com",
        ],
        "font-src": ["fonts.gstatic.com"],
        "img-src": [
            "'self'",
            "www.gstatic.com",
            # Required for user avatars from GitHub, Google.
            "*.githubusercontent.com",
            "*.googleusercontent.com",
        ],
        "connect-src": ["'self'", "www.googleapis.com"],
        "frame-src": ["https://conducthotline-fb.firebaseapp.com/"],
    },
)

app.register_blueprint(hotline.telephony.webhandlers.blueprint)
app.register_blueprint(hotline.auth.webhandlers.blueprint)
app.register_blueprint(hotline.events.webhandlers.blueprint)
app.register_blueprint(hotline.pages.webhandlers.blueprint)
app.register_blueprint(hotline.numberadmin.webhandlers.blueprint)


@app.template_filter("phone")
def phone_format_filter(s):
    try:
        number = phonenumbers.parse(s, "US")
        return phonenumbers.format_number(
            number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
    except phonenumbers.NumberParseException:
        return s


@app.context_processor
def add_csrf_field_processor():
    def csrf_field():
        csrf_token = app.jinja_env.globals["csrf_token"]()
        return jinja2.Markup(
            f'<input type="hidden" name="_csrf_token" value="{csrf_token}">'
        )

    return dict(csrf_field=csrf_field)


# Add a default root route.
@app.route("/")
def index():
    return flask.redirect(flask.url_for("pages.view_page", name="about"))


@app.errorhandler(404)
def not_found(e):
    return flask.render_template("404.html")


@app.errorhandler(403)
def unauthorized(e):
    return flask.render_template("403.html")


@app.errorhandler(500)
def server_error(e):
    if app.debug:
        return (
            """
        An internal error occurred: <pre>{}</pre>
        See logs for full stacktrace.
        """.format(
                e
            ),
            500,
        )

    return flask.render_template("500.html")


@app.cli.command()
def reset_database():
    from hotline.database.create_tables import create_tables

    create_tables()


@app.cli.command()
@click.argument("number")
@click.argument("sms_callback_url")
def manual_add_number(number, sms_callback_url):
    import hotline.telephony.lowlevel
    from hotline.database import models

    hotline.telephony.lowlevel.setup_number(number, "US", sms_callback_url)

    with models.db:
        number_entry = models.Number()
        number_entry.number = hotline.telephony.lowlevel.normalize_number(number)
        number_entry.country = "US"
        number_entry.save()
