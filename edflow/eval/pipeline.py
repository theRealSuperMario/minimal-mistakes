"""To produce consistent results we adopt the following pipeline:

**Step 1:** Evaluate model on a test dataset and write out all data of interest:

    - generated image
    - latent representations

**Step 2:** Load the generated data in a Datafolder using the EvalDataset

**Step 3:** Pass both the test Dataset and the Datafolder to the evaluation scripts

Sometime in the future:
**(Step 4):** Generate a report:

    - latex tables
    - paths to videos
    - plots

Usage
-----

The pipeline is easily setup: In you Iterator (Trainer or Evaluator) add
the EvalHook and as many callbacks as you like. You can also pass no callback
at all.

.. warning::

    To use the output with ``edeval`` you must set ``config=config``.

.. code-block:: python

    from edflow.eval.pipeline import EvalHook

    def my_callback(root, data_in, data_out, config):
        # Do somethin fancy with the data
        results = ...

        return results

    class MyIterator(PyHookedModelIterator):
        """ """
        def __init__(self, config, root, model, **kwargs):

            self.model = model

            self.hooks += [EvalHook(self.dataset,
                                    callbacks={'cool_cb': my_callback},
                                    config=config,  # Must be specified for edeval
                                    step_getter=self.get_global_step)]

        def eval_op(self, inputs):
            return {'generated': self.model(inputs)}

        self.step_ops(self):
            return self.eval_op


Next you run your evaluation on your data using your favourite edflow command.

.. code-block:: bash

    edflow -n myexperiment -e the_config.yaml -p path_to_project

This will create a new evaluation folder inside your project's eval directory.
Inside this folder everything returned by your step ops is stored. In the case
above this would mean your outputs would be stored as
``generated:index.something``. But you don't need to concern yourself with
that, as the outputs can now be loaded using the :class:`EvalDataFolder`.

All you need to do is pass the EvalDataFolder the root folder in which the data
has been saved, which is the folder where you can find the
``model_outputs.csv``. Now you have all the generated data easily usable at
hand. The indices of the data in the EvalDataFolder correspond to the indices
of the data in the dataset, which was used to create the model outputs. So
you can directly compare inputs, targets etc, with the outputs of your model!

If you specified a callback, this all happens automatically. Each callback
receives at least 4 parameters: The ``root``, where the data lives, the two
datasets ``data_in``, which was fed into the model and ``data_out``, which was
generated by the model, and the ``config``. You can specify additional keyword
arguments by defining them in the config under
``eval_pipeline/callback_kwargs``.

Should you want to run evaluations on the generated data after it has been
generated, you can run the ``edeval`` command while specifying the path
to the model outputs csv and the callbacks you want to run.

.. code-block:: bash

    edeval -c path/to/model_outputs.csv -cb name1:callback1 name2:callback2

The callbacks must be supplied using ``name:callback`` pairs. Names must be
unique as ``edeval`` will construct a dictionary from these inputs.

If at some point you need to specify new parameters in your config or change
existing ones, you can do so exactly like you would when running the ``edflow``
command. Simply pass the parameters you want to add/change via the commandline
like this:

.. code-block:: bash

    edeval -c path/to/model_outputs.csv -cb name1:callback1 --key1 val1 --key/path/2 val2

.. warning::
    Changing config parameters from the commandline adds some dangers to the
    eval worklow: E.g. you can change parameters which determine the
    construction of the generating dataset, which potentially breaks the
    mapping between inputs and outputs.
"""

import os
import numpy as np
import yaml  # metadata
from PIL import Image

from edflow.data.util import adjust_support
from edflow.util import walk, retrieve, pop_keypath
from edflow.data.dataset import DatasetMixin
from edflow.data.believers.meta import MetaDataset
from edflow.project_manager import ProjectManager as P
from edflow.hooks.hook import Hook
from edflow.custom_logging import get_logger


LOADABLE_EXTS = ["png", "npy"]


class EvalHook(Hook):
    """Stores all outputs in a reusable fashion."""

    def __init__(
        self,
        dataset,
        sub_dir_keys=[],
        labels_key=None,
        callbacks={},
        config=None,
        step_getter=None,
        keypath="step_ops",
    ):
        """
        .. warning::
            To work with ``edeval`` you **must** specify ``config=config`` when
            instantiating the EvalHook.

        Parameters
        ----------
            dataset : DatasetMixin
                The Dataset used for creating the new data.
            sub_dir_keys : list(str)
                Keys found in :attr:`example`, which will
                be used to make a subdirectory for the stored example.
                Subdirectories are made in a nested fashion in the order of the
                list. The keys will be removed from the example dict and not be
                stored explicitly.
            labels_key : str
                All data behind the key found in the :attr:`example`s, will be
                stored in large arrays and later loaded as labels. This should
                be small data types like ``int`` or ``str`` or small ``numpy``
                arrays.
            callbacks : dict(name: str or Callable)
                All callbacks are called at the end of the epoch. Must
                accept root as argument as well as the generating dataset and
                the generated dataset and a config (in that order). Additional
                keyword arguments found at ``eval_pipeline/callback_kwargs``
                will also be passed to the callbacks. You can also leave this
                empty and supply import paths via :attr:`config`.
            config : object, dict
                An object containing metadata. Must be dumpable by
                ``yaml``. Usually the ``edflow`` config.
                You can define callbacks here as well. These must be under
                the keypath ``eval_pipeline/callbacks``. Also you can define
                additional keyword arguments passed to the callbacks as
                described in :attr:`callbacks`.
            step_getter : Callable
                Function which returns the global step as ``int``.
            keypath : str
                Path in result which will be stored.
        """
        self.logger = get_logger(self)

        config_cbs = retrieve(config, "eval_pipeline/callbacks", default={})
        callbacks.update(config_cbs)

        self.cb_names = list(callbacks.keys())
        self.cb_paths = list(callbacks.values())

        self.cbacks = load_callbacks(callbacks)
        self.logger.info("{}".format(self.cbacks))

        self.sdks = sub_dir_keys
        self.lk = labels_key
        self.data_in = dataset

        self.config = config

        self.gs = step_getter
        self.keypath = keypath

    def before_epoch(self, epoch):
        """
        Sets up the dataset for the current epoch.
        """
        self.root = os.path.join(P.latest_eval, str(self.gs()))
        self.save_root = os.path.join(self.root, "model_outputs")

        os.makedirs(self.root, exist_ok=True)
        os.makedirs(self.save_root, exist_ok=True)
        os.makedirs(os.path.join(self.save_root, "labels"), exist_ok=True)

        self.label_arrs = None

    def before_step(self, step, fetches, feeds, batch):
        """Get dataset indices from batch."""
        self.idxs = np.array(batch["index_"], dtype=int)

    def after_step(self, step, last_results):
        """Save examples and store label values."""
        if self.lk is not None:
            label_vals = pop_keypath(last_results, self.lk, default={})
        else:
            label_vals = {}

        idxs = self.idxs  # indices collected before_step

        path_dicts = save_output(
            root=self.save_root,
            example=last_results,
            index=idxs,
            sub_dir_keys=self.sdks,
            keypath=self.keypath,
        )

        for idx in idxs:
            for key, path in path_dicts[idx].items():
                if key not in label_vals:
                    label_vals[key] = []

                label_vals[key] += [path]
        for key in list(path_dicts[idxs[0]].keys()):
            label_vals[key] = np.array(label_vals[key])

        if self.label_arrs is None:
            self.label_arrs = {}
            for k in label_vals.keys():
                example = label_vals[k][0]
                ex_shape = list(np.shape(example))
                shape = [len(self.data_in)] + ex_shape
                s = "x".join([str(s) for s in shape])
                dtype = d = example.dtype

                k_ = k.replace("/", "--")
                savepath = os.path.join(
                    self.save_root, "labels", "{}-*-{}-*-{}.npy".format(k_, s, d)
                )
                memmap = np.memmap(savepath, shape=tuple(shape), mode="w+", dtype=dtype)
                self.label_arrs[k] = memmap

        for k in label_vals.keys():
            # Can the inner loop be made a fancy indexing assign?
            for i, idx in enumerate(idxs):
                self.label_arrs[k][idx] = label_vals[k][i]

    def at_exception(self, *args, **kwargs):
        """Save all meta data. The already written data is not lost in any even
        if this fails."""
        self.exception_occured = True
        if hasattr(self, "root"):
            self.save_meta()

        self.logger.info("Warning: Evaluation data is incomplete!")

    def after_epoch(self, epoch):
        """Save meta data for reuse and then start the evaluation callbacks
        """
        self.save_meta()

        data_out = MetaDataset(self.save_root)
        data_out.append_labels = True

        cb_kwargs = retrieve(self.config, "eval_pipeline/callback_kwargs", default={})

        for n, cb in self.cbacks.items():
            cb_name = "CB: {}".format(n)
            cb_name = "{a}\n{c}\n{a}".format(a="=" * len(cb_name), c=cb_name)
            self.logger.info(cb_name)

            kwargs = cb_kwargs.get(n, {})
            cb(self.root, self.data_in, data_out, self.config, **kwargs)

    def save_meta(self):
        """ """

        if not hasattr(self, "exception_occured"):
            had_exception = f"    .. note ::\n\n        No exception encountered during creation.\n\n"
        else:
            had_exception = f"    .. warning ::\n\n        An exception occured during creation.\n\n"

        description = f"    # Model Outputs\n{had_exception}"
        meta_path = add_meta_data(self.save_root, self.config, description)

        cb_names = self.cb_names
        cb_paths = self.cb_paths

        if cb_names:
            cbs = " ".join("{}:{}".format(k, v) for k, v in zip(cb_names, cb_paths))
        else:
            cbs = "<name>:<your callback>"

        self.logger.info("MODEL_OUTPUT_ROOT {}".format(self.save_root))
        self.logger.info(
            "All data has been produced. You can now also run all"
            + " callbacks using the following command:\n"
            + f"edeval -c {self.save_root} -cb {cbs}"
        )
        self.logger.info(
            "To directly reuse the data simply use the following command:\n"
            + "from edflow.data.believers.meta import MetaDataset\n"
            + f'M = MetaDataset("{os.path.abspath(self.save_root)}"\n)'
        )


class TemplateEvalHook(EvalHook):
    """EvalHook that disables itself when the eval op returns None."""

    def before_epoch(self, *args, **kwargs):
        self._active = True
        super().before_epoch(*args, **kwargs)

    def before_step(self, *args, **kwargs):
        if self._active:
            super().before_step(*args, **kwargs)

    def after_step(self, step, last_results):
        tmp = object()
        if retrieve(last_results, self.keypath, default=tmp) in [None, tmp]:
            self._active = False
        if self._active:
            super().after_step(step, last_results)

    def after_epoch(self, *args, **kwargs):
        if self._active:
            super().after_epoch(*args, **kwargs)

    def at_exception(self, *args, **kwargs):
        if self._active:
            super().at_exception(*args, **kwargs)


def save_output(root, example, index, sub_dir_keys=[], keypath="step_ops"):
    """Saves the ouput of some model contained in ``example`` in a reusable
    manner.

    Parameters
    ----------
    root : str
        Storage directory
    example : dict
        name: datum pairs of outputs.
    index : list(int
        dataset index corresponding to example.
    sub_dir_keys : list(str
        Keys found in :attr:`example`, which will be
        used to make a subirectory for the stored example. Subdirectories
        are made in a nested fashion in the order of the list. The keys
        will be removed from the example dict and not be stored.
        Directories are name ``key:val`` to be able to completely recover
        the keys. (Default value = [])

    Returns
    -------
    path_dics : dict
        Name: path pairs of the saved ouputs.

        .. warning:: 
        
            Make sure the values behind the ``sub_dir_keys`` are compatible with
            the file system you are saving data on.

    """

    example = retrieve(example, keypath)

    sub_dirs = [""] * len(index)
    for subk in sub_dir_keys:
        sub_vals = _delget(example, subk)
        for i, sub_val in enumerate(sub_vals):
            name = "{}:{}".format(subk, sub_val)
            name = name.replace("/", "--")
            sub_dirs[i] = os.path.join(sub_dirs[i], name)

    roots = [os.path.join(root, sub_dir) for sub_dir in sub_dirs]
    for r in roots:
        os.makedirs(r, exist_ok=True)

    roots += [root]

    path_dicts = {}
    for i, [idx, root] in enumerate(zip(index, roots)):
        path_dict = {}
        for n, e in example.items():
            savename = "{}_{:0>6d}.{{}}".format(n, idx)
            path = os.path.join(root, savename)

            path, inferred_loader = save_example(path, e[i])

            # Conforms to the meta dataset key style for automatic loading
            path_dict[f"{n}:{inferred_loader}"] = path
        path_dicts[idx] = path_dict

    return path_dicts


def add_meta_data(eval_root, metadata, description=None):
    """Prepends kwargs of interest to a csv file as comments (`#`)

    Parameters
    ----------
    eval_root : str
        Where the `meta.yaml` will be written.
    metadata : dict
        config like object, which will be written in the `meta.yaml`.
    description : str
        Optional description string. Will be added unformatted as yaml
        multiline literal.

    Returns
    -------
    meta_path : str
        Full path of the `meta.yaml`.
    """

    meta_string = yaml.dump(metadata)
    meta_path = os.path.join(eval_root, "meta.yaml")

    with open(meta_path, "w+") as meta_file:
        if description is None:
            description = "Created with the `EvalHook`"
        meta_file.write(f"description: |\n{description}")
        meta_file.write(meta_string)

    return meta_path


def _delget(d, k):
    """
    Gets a value from ``dict`` :attr:`d` at :attr:`k` and returns it, after
    deleting :attr:`k` from :attr:`d`.

    Parameters
    ----------
    d : dict
        Dictionary from which to get the item at :attr:`k`.
    k : str
        Key to be deleted after getting the value behind it.


    Returns
    -------
    v : object
        The value ``d[k]``

    """
    v = d[k]
    del d[k]
    return v


def save_example(savepath, datum):
    """
    Manages the writing process of a single datum: (1) Determine type,
    (2) Choose saver, (3) save.

    Parameters
    ----------
    savepath : str
        Where to save. Must end with `.{}` to put in the
        file ending via `.format()`.
    datum : object
        Some python object to save.

    Returns
    -------
    savepath : str
        Where the example has been saved. This string has been formatted and
        can be used to load the file at the described location.
    loader_name : str
        The name of a loader, which can be passed to the ``meta.yaml`` 's
        ``loaders`` entry.
    """

    saver, ending = determine_saver(datum)
    loader_name = determine_loader(ending)

    savepath = savepath.format(ending)

    saver(savepath, datum)

    return savepath, loader_name


def determine_saver(py_obj):
    """Applies some heuristics to save an object.

    Parameters
    ----------
    py_obj : object
        Some python object to be saved.


    Raises
    -------
    NotImplementedError
        If :attr:`py_obj` is of unrecognized type. Feel free to implement your
        own savers and publish them to edflow.

    """

    if isinstance(py_obj, np.ndarray):
        if isimage(py_obj):
            return image_saver, "png"
        else:
            return np_saver, "npy"

    elif isinstance(py_obj, str):
        return txt_saver, "txt"

    else:
        raise NotImplementedError(
            "There currently is not saver heuristic " + "for {}".format(type(py_obj))
        )


def determine_loader(ext):
    """Returns a loader name for a given file extension
    
    Parameters
    ----------
    ext : str
        File ending excluding the ``.``. Same as what would be returned by
        :func:`os.path.splitext`

    Returns
    -------
    name : str
        Name of the meta loader (see
        :py:mod:`~edflow.data.believers.meta_loaders` .

    Raises
    ------
    ValueError
        If the file extension cannot be handled by the implemented loaders.
        Feel free to implement you own and publish them to ``edflow``.
    """

    if ext == "png":
        return "image"
    elif ext == "npy":
        return "np"
    else:
        raise ValueError("Cannot load file with extension `{}`".format(ext))


def decompose_name(name):
    """

    Parameters
    ----------
    name :


    Returns
    -------

    """
    try:
        splits = name.split("_")
        rest = splits[-1]
        datum_name = "_".join(splits[:-1])
        index, ending = rest.split(".")

        return int(index), datum_name, ending
    except Exception as e:
        print("Faulty name:", name)
        raise e


def is_loadable(filename):
    """

    Parameters
    ----------
    filename :


    Returns
    -------

    """
    if "." in filename:
        name, ext = filename.split(".")
        if ext not in LOADABLE_EXTS:
            return False
        elif name.count("_") != 1:
            return False
        else:
            return True
    else:
        return False


def isimage(np_arr):
    """

    Parameters
    ----------
    np_arr :


    Returns
    -------

    """
    shape = np_arr.shape
    return len(shape) == 3 and shape[-1] in [1, 3, 4]


def image_saver(savepath, image):
    """

    Parameters
    ----------
    savepath :

    image :


    Returns
    -------

    """
    im_adjust = adjust_support(image, "0->255", clip=True)

    modes = {1: "L", 3: "RGB", 4: "RGBA"}
    mode = modes[im_adjust.shape[-1]]
    if mode == "L":
        im_adjust = np.squeeze(im_adjust, -1)

    im = Image.fromarray(im_adjust, mode)

    im.save(savepath)


def np_saver(savepath, np_arr):
    """

    Parameters
    ----------
    savepath :

    np_arr :


    Returns
    -------

    """
    np.save(savepath, np_arr)


def standalone_eval_meta_dset(
    path_to_meta_dir, callbacks, additional_kwargs={}, other_config=None
):
    """Runs all given callbacks on the data in the :class:`EvalDataFolder`
    constructed from the given csv.abs

    Parameters
    ----------
    path_to_csv : str
        Path to the csv file.
    callbacks : dict(name: str or Callable)
        Import commands used to construct the functions applied to the Data
        extracted from :attr:`path_to_csv`.
    additional_kwargs : dict
        Keypath-value pairs added to the config, which is extracted from
        the ``model_outputs.csv``. These will overwrite parameters in the
        original config extracted from the csv.
    other_config : str
        Path to additional config used to update the existing one as taken from
        the ``model_outputs.csv`` . Cannot overwrite the dataset. Only used for
        callbacks. Parameters in this other config will overwrite the
        parameters in the original config and those of the commandline
        arguments.

    Returns
    -------
    outputs: dict
        The collected outputs of the callbacks.
    """

    from edflow.main import get_implementations_from_config
    from edflow.config import update_config
    import yaml

    if other_config is not None:
        with open(other_config, "r") as f:
            other_config = yaml.full_load(f)
    else:
        other_config = {}

    out_data = MetaDataset(path_to_meta_dir)

    config = out_data.meta

    dataset_str = config["dataset"]
    impl = get_implementations_from_config(config, ["dataset"])
    in_data = impl["dataset"](config)

    update_config(config, additional_kwargs)
    config.update(other_config)

    config_callbacks, callback_kwargs = config2cbdict(config)
    callbacks.update(config_callbacks)

    callbacks = load_callbacks(callbacks)

    root = os.path.dirname(path_to_meta_dir)

    outputs = apply_callbacks(
        callbacks, root, in_data, out_data, config, callback_kwargs
    )

    return outputs


def load_callbacks(callbacks):
    """Loads all callbacks, i.e. if the callback is given as str, will load the
    module behind the import path, otherwise will do nothing.
    """
    import importlib
    import sys

    sys.path.append(os.getcwd())  # convenience: load implementations from cwd

    loaded_callbacks = dict()
    for name, cb in callbacks.items():
        if isinstance(cb, str):
            module = ".".join(cb.split(".")[:-1])
            module = importlib.import_module(module)

            cb = getattr(module, cb.split(".")[-1])

            loaded_callbacks[name] = cb
        else:
            loaded_callbacks[name] = cb

    return loaded_callbacks


def apply_callbacks(callbacks, root, in_data, out_data, config, callback_kwargs={}):
    """Runs all given callbacks on the datasets ``in_data`` and ``out_data``.

    Parameters
    ----------
    callbacks : dict(name: Callable)
        List of all callbacks to apply. All callbacks must accept at least the
        signitatue ``callback(root, data_in, data_out, config)``. If supplied
        via the config, additional keyword arguments are passed to the
        callback. These are expected under the keypath
        ``eval_pipeline/callback_kwargs``.
    in_data : DatasetMixin
        Dataset used to generate the content in ``out_data``.
    out_data : DatasetMixin
        Generated data. Example i is expected to be generated using
        ``in_data[i]``.
    config : dict
        edflow config dictionary.
    callback_kwargs : dict
        Keyword Arguments for the callbacks.

    Returns
    -------
    outputs : dict(name: callback output)
        All results generated by the callbacks at the corresponding key.
    """

    outputs = {}
    for name, cb in callbacks.items():
        kwargs = callback_kwargs.get(name, {})
        outputs[name] = cb(root, in_data, out_data, config, **kwargs)

    return outputs


def cbargs2cbdict(arglist):
    """Turns a list of ``name:callback`` into a dict ``{name: callback}``"""

    out = {}
    for arg in arglist:
        splits = arg.split(":")
        if len(splits) != 2:
            raise ValueError(
                "Callbacks must be supplied via the commandline "
                "using `name:import_path` pairs."
            )
        name, cb = splits
        out[name] = cb

    return out


def config2cbdict(config):
    """Extracts the callbacks inside a config and returns them as dict.
    Callbacks must be defined at ``eval_pipeline/callback_kwargs``.
    
    Parameters
    ----------
    config : dict
        A config dictionary. 

    Returns
    -------
    callbacks : dict
        All name:callback pairs as ``dict`` ``{name: callback}``
    """

    callbacks = retrieve(config, "eval_pipeline/callbacks", default={})
    kwargs = retrieve(config, "eval_pipeline/callback_kwargs", default={})

    return callbacks, kwargs


def main():
    import argparse
    from edflow.config import parse_unknown_args

    import sys

    sys.path.append(os.getcwd())  # convenience: load implementations from cwd

    A = argparse.ArgumentParser(
        description="""
Use edeval for running callbacks on data generated using the
``edflow.eval_pipeline.eval_pipeline.EvalHook``. Once the data is created all
you have to do is pass the ``csv``-file created by the hook. It specifies all
the relevant information: Which dataset was used to create the data, along with
all config parameters and where all generated samples live.

Callbacks will be evaluated in the order they have been passed to this
function. They must be supplied in `name:callback` pairs.

For more documentation take a look at ``edflow/eval_pipeline/eval_pipeline.py``
"""
    )

    A.add_argument(
        "-c",
        "--csv",
        default="model_output.csv",
        type=str,
        help="path to a csv-file created by the EvalHook containing"
        " samples generated by a model.",
    )
    A.add_argument(
        "-cb",
        "--callback",
        type=str,
        nargs="*",
        help="Import string to the callback functions used for the "
        "standalone evaluation.",
    )
    A.add_argument(
        "-cf",
        "--other_config",
        type=str,
        default=None,
        help="Other config, which can be used to e.g. update eval_pipeline related "
        "parameters, but also others.",
    )

    args, unknown = A.parse_known_args()
    additional_kwargs = parse_unknown_args(unknown)

    callbacks = cbargs2cbdict(args.callback)

    standalone_eval_meta_dset(args.csv, callbacks, additional_kwargs, args.other_config)


if __name__ == "__main__":
    main()
