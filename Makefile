# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only

KERNEL_ROOT ?= .

CC ?= cc
AR ?= ar
MPFR_PREFIX ?= $(shell brew --prefix mpfr 2>/dev/null)
GMP_PREFIX ?= $(shell brew --prefix gmp 2>/dev/null)

CPPFLAGS ?=
CPPFLAGS += -I$(KERNEL_ROOT)/include
CFLAGS ?= -O2 -g -Wall -Wextra -Wpedantic
LDFLAGS ?=
LDLIBS ?=

ifneq ($(MPFR_PREFIX),)
CPPFLAGS += -I$(MPFR_PREFIX)/include
LDFLAGS += -L$(MPFR_PREFIX)/lib
endif
ifneq ($(GMP_PREFIX),)
CPPFLAGS += -I$(GMP_PREFIX)/include
LDFLAGS += -L$(GMP_PREFIX)/lib
endif

LDLIBS += -lmpfr -lgmp -lm

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
SHARED_EXT := dylib
SHARED_LDFLAGS := -dynamiclib
else
SHARED_EXT := so
SHARED_LDFLAGS := -shared
endif

# Supported direct GCC/Clang commands; opaque wrappers/response options cannot
# establish the floating-point contract by a final driver suffix alone.
GI_NATIVE_COMPILER := $(notdir $(firstword $(CC)))
ifeq ($(filter cc gcc gcc-% clang clang-%,$(GI_NATIVE_COMPILER)),)
$(error Native builds require a direct GCC/Clang compiler command)
endif
GI_UNSUPPORTED_NATIVE_FLAGS := -Ofast -ffast-math -ffinite-math-only -funsafe-math-optimizations -fassociative-math -freciprocal-math -fno-signed-zeros -fno-rounding-math -fno-trapping-math -fexcess-precision=fast -fcx-limited-range -fapprox-func -ffp-contract=fast -ffp-contract=on -ffp-model=% -flto% -fplugin% @% -Xclang -Xpreprocessor -Xassembler -Xlinker -mllvm -Wa,% -Wl,@% -Wl,-plugin% -Wl,--plugin% -Wp,% -fdenormal-fp-math% -mdaz-ftz -munsafe-fp-math -mno-ieee-fp -fno-honor-infinities -fno-honor-nans
GI_REQUESTED_NATIVE_FLAGS := $(CC) $(CPPFLAGS) $(CFLAGS) $(LDFLAGS) $(SHARED_LDFLAGS) $(LDLIBS)
GI_REJECTED_NATIVE_FLAGS := $(filter $(GI_UNSUPPORTED_NATIVE_FLAGS),$(GI_REQUESTED_NATIVE_FLAGS))
ifneq ($(GI_REJECTED_NATIVE_FLAGS),)
$(error Unsupported native floating-point/opaque flags: $(GI_REJECTED_NATIVE_FLAGS))
endif
# These channels occur after CFLAGS when compiling native test executables.
# Reject late assertion disablement, including split -D NDEBUG spelling.
GI_LATE_ASSERTION_FLAGS := $(filter -DNDEBUG% NDEBUG%,$(LDFLAGS) $(SHARED_LDFLAGS) $(LDLIBS))
ifneq ($(GI_LATE_ASSERTION_FLAGS),)
$(error Unsupported native late assertion flags: $(GI_LATE_ASSERTION_FLAGS))
endif
# override is necessary when CFLAGS was supplied on the make command line.
# UNDEBUG separately keeps native numerical assertions active.
override CFLAGS += -std=c11 -fno-fast-math -frounding-math -ffp-contract=off -fPIC -UNDEBUG

BUILD_DIR ?= build
.DEFAULT_GOAL := all
OBJECTS := $(BUILD_DIR)/interval.o $(BUILD_DIR)/common_factor.o $(BUILD_DIR)/remainder.o $(BUILD_DIR)/transcendental.o
LIB := $(BUILD_DIR)/libgraphing.a
SHARED_LIB := $(BUILD_DIR)/libgraphing.$(SHARED_EXT)
EXACT_INPUTS_TEST := $(BUILD_DIR)/test_exact_inputs
INTERVAL_TEST := $(BUILD_DIR)/test_interval
COMMON_FACTOR_TEST := $(BUILD_DIR)/test_common_factor
TRANSCENDENTAL_TEST := $(BUILD_DIR)/test_transcendental
REMAINDER_TEST := $(BUILD_DIR)/test_remainder
INTERVAL_SOURCE ?= $(KERNEL_ROOT)/src/interval.c
COMMON_FACTOR_SOURCE ?= $(KERNEL_ROOT)/src/common_factor.c
TRANSCENDENTAL_SOURCE ?= $(KERNEL_ROOT)/src/transcendental.c
REMAINDER_SOURCE ?= $(KERNEL_ROOT)/src/remainder.c
LIB_OBJECTS := $(OBJECTS)

# Make does not otherwise notice flags, toolchain, or source-override changes.
# Pass effective values through exports (recipes) or shell-quoted assignments (inspection).
GI_MAKEFILE_INPUTS := $(MAKEFILE_LIST)
BUILD_CONFIG_KEYS := GI_MAKEFILE_INPUTS CC AR CPPFLAGS CFLAGS LDFLAGS LDLIBS MPFR_PREFIX GMP_PREFIX INTERVAL_SOURCE COMMON_FACTOR_SOURCE TRANSCENDENTAL_SOURCE REMAINDER_SOURCE
$(foreach key,$(BUILD_CONFIG_KEYS),$(eval export GI_BUILD_$(key) := $($(key))))
C_TEST_BINARIES := $(EXACT_INPUTS_TEST) $(INTERVAL_TEST) $(COMMON_FACTOR_TEST) $(REMAINDER_TEST) $(TRANSCENDENTAL_TEST)
export GI_BUILD_PRODUCTS := $(OBJECTS) $(BENCHMARK_OBJECTS) $(LIB) $(SHARED_LIB) $(BENCHMARK_LIB) $(C_TEST_BINARIES)
BUILD_CONFIG := $(BUILD_DIR)/.build-config.json
# Read-only during parsing, including make -n. Force changed configurations even
# on hosts whose Make compares timestamps at whole-second resolution.
shell_quote = '$(subst ','"'"',$(1))'
BUILD_CONFIG_ENV = $(foreach key,$(BUILD_CONFIG_KEYS),GI_BUILD_$(key)=$(call shell_quote,$($(key)))) GI_BUILD_PRODUCTS=$(call shell_quote,$(GI_BUILD_PRODUCTS))
BUILD_CONFIG_STATUS := $(shell $(BUILD_CONFIG_ENV) python3 $(KERNEL_ROOT)/tools/native-build-config.py "$(BUILD_CONFIG)" --check)
ifeq ($(filter $(BUILD_CONFIG_STATUS),changed unchanged),)
$(error Could not inspect native build configuration)
endif
ifeq ($(BUILD_CONFIG_STATUS),changed)
.PHONY: $(GI_BUILD_PRODUCTS)
endif
DEPFLAGS = -MD -MP -MF $@.d

.PHONY: FORCE
FORCE:

$(BUILD_CONFIG): FORCE | $(BUILD_DIR)
	python3 $(KERNEL_ROOT)/tools/native-build-config.py "$(BUILD_CONFIG)"

# Include compiler-discovered transitive and system headers for every compile.
ifeq ($(BUILD_CONFIG_STATUS),unchanged)
-include $(wildcard $(addsuffix .d,$(GI_BUILD_PRODUCTS)))
endif

$(OBJECTS) $(BENCHMARK_OBJECTS): $(BUILD_CONFIG)

.PHONY: all shared test test-c check-brand-copy clean

all: $(LIB) $(SHARED_LIB)

shared: $(SHARED_LIB)

test: check-brand-copy test-c

check-brand-copy:
	python3 "$(KERNEL_ROOT)/tools/check-brand-copy.py"
	python3 -m unittest discover -s "$(KERNEL_ROOT)/tests" -p test_brand_copy.py

test-c: $(C_TEST_BINARIES)
	$(EXACT_INPUTS_TEST)
	$(INTERVAL_TEST)
	$(COMMON_FACTOR_TEST)
	$(REMAINDER_TEST)
	$(TRANSCENDENTAL_TEST)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/interval.o: $(INTERVAL_SOURCE) $(KERNEL_ROOT)/include/graphing/interval.h | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(DEPFLAGS) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/common_factor.o: $(COMMON_FACTOR_SOURCE) $(KERNEL_ROOT)/include/graphing/common_factor.h $(KERNEL_ROOT)/include/graphing/interval.h | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(DEPFLAGS) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/remainder.o: $(REMAINDER_SOURCE) $(KERNEL_ROOT)/include/graphing/remainder.h $(KERNEL_ROOT)/include/graphing/interval.h | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(DEPFLAGS) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/transcendental.o: $(TRANSCENDENTAL_SOURCE) $(KERNEL_ROOT)/include/graphing/transcendental.h $(KERNEL_ROOT)/include/graphing/interval.h | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(DEPFLAGS) $(CFLAGS) -c $< -o $@

$(LIB): $(LIB_OBJECTS)
	rm -f $@
	$(AR) rcs $@ $^

$(SHARED_LIB): $(OBJECTS)
	$(CC) $(SHARED_LDFLAGS) $(LDFLAGS) $^ $(LDLIBS) -o $@

$(INTERVAL_TEST): $(KERNEL_ROOT)/tests/test_interval.c $(KERNEL_ROOT)/include/graphing/common_factor.h $(KERNEL_ROOT)/include/graphing/remainder.h $(LIB) | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(DEPFLAGS) $(CFLAGS) $< $(LIB) $(LDFLAGS) $(LDLIBS) -o $@

$(EXACT_INPUTS_TEST): $(KERNEL_ROOT)/tests/test_exact_inputs.c $(LIB) | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(DEPFLAGS) $(CFLAGS) $< $(LIB) $(LDFLAGS) $(LDLIBS) -o $@

$(COMMON_FACTOR_TEST): $(KERNEL_ROOT)/tests/test_common_factor.c $(KERNEL_ROOT)/include/graphing/common_factor.h $(LIB) | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(DEPFLAGS) $(CFLAGS) $< $(LIB) $(LDFLAGS) $(LDLIBS) -o $@

$(TRANSCENDENTAL_TEST): $(KERNEL_ROOT)/tests/test_transcendental.c $(LIB) | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(DEPFLAGS) $(CFLAGS) $< $(LIB) $(LDFLAGS) $(LDLIBS) -o $@

$(REMAINDER_TEST): $(KERNEL_ROOT)/tests/test_remainder.c $(LIB) | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(DEPFLAGS) $(CFLAGS) $< $(LIB) $(LDFLAGS) $(LDLIBS) -o $@

clean:
	rm -rf $(BUILD_DIR)
