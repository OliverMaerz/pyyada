# pyyada
Simple blog written in python for Udacity class

This software requires the Google Cloud SDK for Python. If you do not have it already installed then download and install from https://cloud.google.com/appengine/docs/python/download.

To run the blog on your local machine you need to first clone the repository with `git clone https://github.com/OliverMaerz/pyyada.git`. Then change into the newly created `pyyada` directory. In the `pyyada` directory run `dev_appserver.py` to start the local web server. You can then access the site at http://localhost:8080. In case you have changed the port then replace 8080 with the port you have configured. 

To run the blog on the Google App Engine you need to additionally setup a project in your Google App Engine account. Once the project is setup make sure you are in the  `pyyada` directory and then run `gcloud app deploy --project your-project` (replace your-project with the name of the project you have configured in the Google App Engine). 


TODO 
- [ ] Work on usability (show edit, delete etc. only if users is owner of post etc.)
- [ ] Add WYSIWYG editor 

CHANGELOG 
 - Intitial version
  
