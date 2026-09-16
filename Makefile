.PHONY: gen-version

all:  gen-version

gen-version:
	git describe --tags --always
	git describe --tags --always | sed 's/v/ /g' | sed 's/\./ /g' | sed 's/-/ /g' | awk '{print ($$1*16777216)+($$2*65536)+($$3*256)+$$4}'
