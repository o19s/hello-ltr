FROM elasticsearch:6.5.2
 
# Install the LTR plugin matching the ES version above, LTR initialization will be performed via notebook.
RUN ./bin/elasticsearch-plugin install http://es-learn-to-rank.labs.o19s.com/ltr-1.1.0-es6.5.2.zip -b
