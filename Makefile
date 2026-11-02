KDIR ?= /lib/modules/$(shell uname -r)/build
.PHONY: all clean test
all:
	./packaging/dkms-build.sh "$(shell uname -r)" "$(KDIR)"
clean:
	$(MAKE) -C "$(KDIR)" M="$(CURDIR)/driver" clean
test:
	python3 -m unittest discover -s tests -v
