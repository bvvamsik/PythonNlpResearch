#NOTE - need to SOURCE this file, running with sh won't work
# only works with ipython for some reason
. activate tensorflow_gpu
export CUDA_VISIBLE_DEVICES=""
ipython /Users/simon.hughes/GitHub/tensorflow_models/tutorials/rnn/translate/translate.py -- --data_dir "/Users/simon.hughes/data/tensorflow/translate/cb/data_dir" --train_dir "/Users/simon.hughes/data/tensorflow/translate/cb/train_dir" --from_train_data "/Users/simon.hughes/data/tensorflow/translate/cb/Training/inputs.txt" --to_train_data "/Users/simon.hughes/data/tensorflow/translate/cb/Training/output_most_freq.txt" --from_dev_data "/Users/simon.hughes/data/tensorflow/translate/cb/Test/inputs.txt" --to_dev_data "/Users/simon.hughes/data/tensorflow/translate/cb/Test/output_most_freq.txt" --learning_rate=0.2 --size=256 --batch_size=16 --from_vocab_size=4300 --to_vocab_size=14 --num_layers=1 --steps_per_checkpoint=100