CARTS_DIR=.
SOURCES_DIR=carts-source
BUILD_DIR=carts-source/build
RELEASE_DIR=latest

EXAMPLES_DIR=carts-examples

compile:
	cd ${SOURCES_DIR}; \
	ant compile

run:
	java -cp ${SOURCES_DIR}/build Carts
	
all:
	cd ${SOURCES_DIR}; \
	ant compile; \
	cd build; \
	jar cvfm Carts.jar ../../Manifest.mf Carts.class com edu ptolemy; \
	rm -rf Carts.class com edu prolemy;\
	cd ..; \
	mv build carts-bin; \
	cp -r examples license.txt readme.txt carts-bin/.; \
	zip -r carts-bin.zip carts-bin; \
	mv carts-bin.zip ..; \
	rm -rf carts-bin; \
	cd ..; \
	zip -r carts-source.zip carts-source
	mkdir ${RELEASE_DIR}; \
	mv carts-bin.zip carts-source.zip ${RELEASE_DIR}/.

	
