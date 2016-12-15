import os
import re
import random
import hashlib
import hmac
from string import letters

import webapp2
import jinja2

from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir),
                               autoescape=True)

secret = 'sfrtsgh98'


def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)


def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())


def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val


class BlogHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))


def render_post(response, post):
    response.out.write('<b>' + post.subject + '</b><br>')
    response.out.write(post.content)


# User related functions

def make_salt(length=5):
    """Create salt used for password hashing."""
    return ''.join(random.choice(letters) for x in xrange(length))


def make_pw_hash(name, pw, salt=None):
    """Hash a password with sha256."""
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)


def valid_pw(name, password, h):
    """Verify a password hash to see if the entered password is ok."""
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)


def users_key(group='default'):
    """Return unique key for users datastore entity"""
    return db.Key.from_path('users', group)


class User(db.Model):
    """User class used for login, register etc. """
    name = db.StringProperty(required=True)
    pw_hash = db.StringProperty(required=True)
    email = db.StringProperty()

    @classmethod
    def by_id(cls, uid):
        return User.get_by_id(uid, parent=users_key())

    @classmethod
    def by_name(cls, name):
        u = User.all().filter('name =', name).get()
        return u

    @classmethod
    def register(cls, name, pw, email=None):
        pw_hash = make_pw_hash(name, pw)
        return User(parent=users_key(),
                    name=name,
                    pw_hash=pw_hash,
                    email=email)

    @classmethod
    def login(cls, name, pw):
        u = cls.by_name(name)
        if u and valid_pw(name, pw, u.pw_hash):
            return u


# Blog related functions

def blog_key(name='default'):
    return db.Key.from_path('blogs', name)


class Post(db.Model):
    """Post model holding data for blog entries"""
    subject = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)
    owner = db.ReferenceProperty(User)
    likes = db.IntegerProperty(default=0)

    def render(self):
        self._render_text = self.content.replace('\n', '<br>')
        return render_str("post.html", p=self)

    @classmethod
    def by_id(cls, post_id):
        return Post.get_by_id(post_id, parent=blog_key())


class Comment(db.Model):
    """Comment model holding data for blog post's comments"""
    content = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)
    owner = db.ReferenceProperty(User)

    def render(self, loggedin):
        self._render_text = self.content.replace('\n', '<br>')
        return render_str("singlecomment.html", content=self.content,
                          loggedin=loggedin, comment_id=self.key().id(),
                          post_id=self.parent().key().id())


class Like(db.Model):
    """Likes model pointing to post and user for each like"""
    post = db.ReferenceProperty(Post)
    user = db.ReferenceProperty(User)


class BlogFront(BlogHandler):
    """Display the blog front page with all posts"""
    def get(self):
        posts = Post.all().order('-created')
        self.render('front.html', posts=posts)


class BlogFrontOld(BlogHandler):
    """Old blog url - redirect to / instead"""
    def get(self):
        self.redirect('/')


class PostPage(BlogHandler):
    """Display a single blog post"""
    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        post = db.get(key)

        if not post:
            self.error(404)
            return

        # get comments only for this post
        comments = Comment.all()
        comments.ancestor(key).order('-created')

        loggedin = False
        if self.user:
            loggedin = True

        self.render("permalink.html", post=post, comments=comments,
                    loggedin=loggedin)


class NewPost(BlogHandler):
    """Display the add post form if user is logged in or otherwise redirect
       to login."""
    def get(self):
        if self.user:
            self.render("editpost.html", title='New')
        else:
            self.redirect("/login")

    def post(self):
        if not self.user:
            self.redirect('/blog')

        subject = self.request.get('subject')
        content = self.request.get('content')

        if subject and content:
            p = Post(parent=blog_key(), subject=subject, content=content,
                     owner=self.user)
            p.put()
            self.redirect('/blog/%s' % str(p.key().id()))
        else:
            error = "Please enter subject and content!"
            self.render("editpost.html", title='New', subject=subject,
                        content=content, error=error)


USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")


def valid_username(username):
    return username and USER_RE.match(username)


PASS_RE = re.compile(r"^.{3,20}$")


def valid_password(password):
    return password and PASS_RE.match(password)


EMAIL_RE = re.compile(r'^[\S]+@[\S]+\.[\S]+$')


def valid_email(email):
    return not email or EMAIL_RE.match(email)


class Signup(BlogHandler):
    def get(self):
        self.render("signup-form.html")

    def post(self):
        have_error = False
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')

        params = dict(username=self.username,
                      email=self.email)

        if not valid_username(self.username):
            params['error_username'] = "That's not a valid username."
            have_error = True

        if not valid_password(self.password):
            params['error_password'] = "That wasn't a valid password."
            have_error = True
        elif self.password != self.verify:
            params['error_verify'] = "Your passwords didn't match."
            have_error = True

        if not valid_email(self.email):
            params['error_email'] = "That's not a valid email."
            have_error = True

        if have_error:
            self.render('signup-form.html', **params)
        else:
            self.done()

    def done(self, *a, **kw):
        raise NotImplementedError


class Register(Signup):
    """Register a new user"""
    def done(self):
        # make sure the user doesn't already exist
        u = User.by_name(self.username)
        if u:
            msg = 'That user already exists.'
            self.render('signup-form.html', error_username=msg)
        else:
            u = User.register(self.username, self.password, self.email)
            u.put()

            self.login(u)
            self.redirect('/welcome')


class Login(BlogHandler):
    """Authenticate a user"""
    def get(self):
        self.render('login-form.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        u = User.login(username, password)
        if u:
            self.login(u)
            self.redirect('/welcome')
        else:
            msg = 'Invalid login'
            self.render('login-form.html', error=msg)


class Logout(BlogHandler):
    """Log out current user"""
    def get(self):
        self.logout()
        self.redirect('/signup')


class Welcome(BlogHandler):
    """Show welcome template if user is logged in; otherwise redirect to
       signup"""
    def get(self):
        if self.user:
            self.render('welcome.html', username=self.user.name)
        else:
            self.redirect('/signup')


class EditPost(BlogHandler):
    """Display form to edit post"""
    def get(self, post_id):
        if self.user:
            key = db.Key.from_path('Post', int(post_id), parent=blog_key())
            post = db.get(key)

            # check if user is author
            if self.user.key() != post.owner.key():
                error = 'You can only edit your own posts'
                self.render('error.html', error=error,
                            url='/blog/%s' % post_id)
                return

            if not post:
                self.error(404)
                return

            self.render('editpost.html', title='Edit', action='/edit',
                        subject=post.subject, content=post.content,
                        post_id=post_id)
        else:
            self.redirect('/login')

    # post with page details submitted ...
    def post(self):
        if not self.user:
            self.redirect('/login')

        post_id = self.request.get('post_id')
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        post = db.get(key)

        # check if user is author
        if self.user.key() != post.owner.key():
            error = 'You can only edit your own posts'
            self.render('error.html', error=error, url='/blog/%s' % post_id)
            return

        subject = self.request.get('subject')
        content = self.request.get('content')

        if subject and content:
            post.subject = subject
            post.content = content
            post.put()
            self.redirect('/blog/%s' % post_id)
        else:
            error = "Please enter subject and content!"
            self.render("editpost.html", title='Edit', action='/edit',
                        subject=subject, content=content, post_id=post_id,
                        error=error)


class DeletePost(BlogHandler):
    """Delete a post"""
    def get(self, post_id):
        if self.user:
            key = db.Key.from_path('Post', int(post_id), parent=blog_key())
            post = db.get(key)

            # check if user is author
            if self.user.key() != post.owner.key():
                error = 'You can only delete your own posts!'
                self.render('error.html', error=error,
                            url='/blog/%s' % str(post_id))
                return

            if not post:
                self.error(404)
                return

            confirmation = self.request.get('confirmation')
            if confirmation == 'yes':
                # user has confirmed deletion
                post.delete()
                self.redirect('/')
            else:
                # show the confirmation page
                self.render('confirmation.html', post_id=post_id)
        else:
            self.redirect('/login')


class CommentPage(BlogHandler):
    """Display form to add a comment to a post and receive the submission
       via post"""
    def get(self, post_id):
        if not self.user:
            self.redirect('/login')

        self.render('comment.html', post_id=post_id)

    def post(self, post_id):
        if not self.user:
            self.redirect('/login')

        content = self.request.get('content')
        # post_id = self.request.get('post_id')

        if content:
            comment = Comment(parent=Post.by_id(int(post_id)),
                              content=content, owner=self.user)
            comment.put()
            self.redirect('/blog/%s' % post_id)
        else:
            error = "Please enter your comment text!"
            self.render("comment.html", content=content, error=error,
                        post_id=post_id)


class DeleteComment(BlogHandler):
    """Delete a post"""
    def get(self, post_id, comment_id):
        if self.user:
            key = db.Key.from_path('Comment', int(comment_id),
                                   parent=db.Key.from_path('Post',
                                                           int(post_id),
                                                           parent=blog_key()))
            comment = db.get(key)

            # check if user is author of comment
            if self.user.key() != comment.owner.key():
                error = 'You can only delete your own comments!'
                self.render('error.html', error=error,
                            url='/blog/%s' % str(post_id))
                return

            if not comment:
                self.error(404)
                return

            confirmation = self.request.get('confirmation')
            if confirmation == 'yes':
                # user has confirmed deletion
                comment.delete()
                self.redirect('/blog/%s' % post_id)
            else:
                # show the confirmation page
                self.render('confirmation.html', post_id=post_id)
        else:
            self.redirect('/login')


class LikePost(BlogHandler):
    """Like a post. Increases like counter."""
    def get(self, post_id):
        if self.user:
            key = db.Key.from_path('Post', int(post_id), parent=blog_key())
            post = db.get(key)
            # check if user is not onwer of post
            if self.user.key() != post.owner.key():
                # check if user has not already liked the post
                likes = Like.all().filter('user =',
                                          self.user.key()).filter('post =',
                                                                  post.key())
                if not likes.get():
                    # now store the user and post in the like table
                    like = Like(post=post, user=self.user)
                    like.put()
                    # ... and increase the number of likes in the post table
                    post.likes = post.likes + 1
                    post.put()

                    # redirect back to the blog entry
                    self.redirect('/blog/%s' % post_id)
                else:
                    error = 'You have already liked this post in the past.'
                    self.render('error.html', error=error,
                                url='/blog/%s' % post_id)
            else:
                error = 'You can not like your own post.'
                self.render('error.html', error=error,
                            url='/blog/%s' % post_id)
        else:
            self.redirect('/login')


# define all the url's and what classe's get or post method to call
app = webapp2.WSGIApplication([('/', BlogFront),
                               ('/welcome', Welcome),
                               ('/blog/?', BlogFrontOld),
                               ('/blog/([0-9]+)', PostPage),
                               ('/blog/newpost', NewPost),
                               ('/signup', Register),
                               ('/login', Login),
                               ('/logout', Logout),
                               ('/edit/([0-9]+)', EditPost),
                               ('/edit', EditPost),
                               ('/like/([0-9]+)', LikePost),
                               ('/comment/([0-9]+)', CommentPage),
                               ('/delete/([0-9]+)', DeletePost),
                               ('/deletecomment/([0-9]+)/([0-9]+)',
                                DeleteComment)
                               ],
                              debug=True)
