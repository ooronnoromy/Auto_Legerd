import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR=Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
SECRET_KEY=os.getenv('SECRET_KEY','DEV-ONLY-CHANGE-ME-BEFORE-DEPLOYMENT')
DEBUG=os.getenv('DJANGO_DEBUG','true').lower()=='true'
ALLOWED_HOSTS=os.getenv('ALLOWED_HOSTS','127.0.0.1,localhost').split(',')
CSRF_TRUSTED_ORIGINS=[x for x in os.getenv('CSRF_TRUSTED_ORIGINS','').split(',') if x]
INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','ledger']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='config.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.debug','django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='config.wsgi.application'
if os.getenv('DATABASE_URL'):
 DATABASES={'default':dj_database_url.parse(os.environ['DATABASE_URL'],conn_max_age=60,conn_health_checks=True)}
elif os.getenv('USE_SQLITE', 'true' if DEBUG and not os.getenv('POSTGRES_HOST') else 'false').lower()=='true':
 DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
else:
 DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('POSTGRES_DB','autoledger'),'USER':os.getenv('POSTGRES_USER','autoledger'),'PASSWORD':os.getenv('POSTGRES_PASSWORD','autoledger_dev'),'HOST':os.getenv('POSTGRES_HOST','localhost'),'PORT':os.getenv('POSTGRES_PORT','5432')}}
AUTH_USER_MODEL='ledger.User'
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='en-us'; TIME_ZONE='Asia/Dhaka'; USE_I18N=True; USE_TZ=True
STATIC_URL='static/'; STATIC_ROOT=BASE_DIR/'staticfiles'; STATICFILES_DIRS=[BASE_DIR/'static']
MEDIA_URL='/media/'; MEDIA_ROOT=Path(os.getenv('MEDIA_ROOT', BASE_DIR/'media'))
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LOGIN_URL='login'; LOGIN_REDIRECT_URL='dashboard'; LOGOUT_REDIRECT_URL='login'
SECURE_CONTENT_TYPE_NOSNIFF=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SECURE=not DEBUG
CSRF_COOKIE_SECURE=not DEBUG
PUSH_VAPID_PUBLIC_KEY=os.getenv('PUSH_VAPID_PUBLIC_KEY','')
PUSH_VAPID_PRIVATE_KEY=os.getenv('PUSH_VAPID_PRIVATE_KEY','')
PUSH_VAPID_SUBJECT=os.getenv('PUSH_VAPID_SUBJECT','')
