./build/NULL/gem5.debug configs/example/garnet_synth_traffic.py \
--num-cpus=64 --num-dirs=64 \
--caches --l1d_size=64kB --l1d_assoc=8 --l1i_size=32kB --l1i_assoc=8 --l2cache --num-l2caches=32 --mem-type=SimpleMemory --mem-size=8GB \
--ruby --network=garnet --topology=SimpleChiplet --mesh-rows=4 --num-chiplets=4 --concentration-factor=4 --num-mem-ctrls=16 \
--sim-cycles=1000000 \
--synthetic=uniform_random --injectionrate=0.02 
#-c tests/test-progs/hello/bin/x86/linux/hello
