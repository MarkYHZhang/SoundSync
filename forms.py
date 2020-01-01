from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired


class CreateForm(FlaskForm):
    yt_url = StringField('Youtube URL', validators=[DataRequired()])
    submit = SubmitField('Sync')


class JoinForm(FlaskForm):
    sync_code = StringField('Sync Code', validators=[DataRequired()])
    submit = SubmitField('join')


