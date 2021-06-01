from __future__ import annotations
from typing import Union

import logging
import json
import subprocess
import yaml

from typing import List

from .dataclasses import DVCParams, SlurmConfig, Files

log = logging.getLogger(__file__)


class DVCOp:
    def __init__(self):
        self._parameters: dict = {}
        self._id: int = 0
        self._running = False  # is set to true, when run_dvc
        self.dvc: DVCParams = DVCParams()
        self.slurm_config: SlurmConfig = SlurmConfig()

        self._json_file = f"{self.name}.json"

    def __repr__(self):
        return self.dvc.__repr__()

    def run_dvc(self, id_=0):
        raise NotImplementedError('Implemented in child class')

    def post_call(self, force=False, exec_=False, always_changed=False, slurm=False):
        self.dvc.make_paths()
        self._write_parameters()
        self._write_dvc(force, exec_, always_changed, slurm)

    def pre_run(self, id_):
        self._running = True
        self.id = id_

    def _write_parameters(self):
        """Update parameters file

        Notes
        -----
        We use this method, because all_parameters is getting updated, so no information is lost.
        We can not write the parameters without caching the old / other parameters first
        """
        self.all_parameters = self.parameters

    @property
    def id(self) -> str:
        """Get multi_use id"""
        if self._running:
            return str(self._id)

        if self.dvc.multi_use:
            if self.all_parameters.get(self.name) is None:
                self._id = 0
            else:
                id_ = len(self.all_parameters[self.name])  # assume that the configuration is new and create a new id_
                for stage_id in self.all_parameters[self.name]:
                    if self.all_parameters[self.name][stage_id] == self.parameters:
                        id_ = stage_id  # entry already exists, load existing id_
                self._id = id_
        else:
            self._id = 0

        return str(self._id)

    @id.setter
    def id(self, value):
        if not self._running:
            raise ValueError('Can only set the value of id during dvc_run!')
        self._id = value

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def module(self) -> str:
        return self.__class__.__module__

    @property
    def stage_name(self) -> str:
        return f"{self.name}_{self.id}"

    @property
    def parameters(self) -> dict:
        if len(self._parameters) > 0:
            # Assume that the value is set, e.g. during the call method
            return self._parameters
        else:
            # Try to read the value from a file, it it hasn't been set
            try:
                return self.all_parameters[self.name][self.id]
            except KeyError:
                return self._parameters  # == return {}

    @parameters.setter
    def parameters(self, value):
        self._parameters = value

    @property
    def all_parameters(self) -> dict:
        """Load ALL parameters from params_file"""
        try:
            with open(self.dvc.params_file_path / self.dvc.params_file) as json_file:
                return json.load(json_file)
        except FileNotFoundError:
            log.debug(f"Could not load params from {self.dvc.params_file_path / self.dvc.params_file}!")
        return {}

    @all_parameters.setter
    def all_parameters(self, value):
        """Update parameters in params_file"""
        if isinstance(value, dict):
            parameters = self.all_parameters
            try:
                parameters[self.name].update({self.id: value})
                log.debug("Updating existing stage")
            except KeyError:
                log.debug(f"Creating a new stage for {self.name}")
                parameters.update({self.name: {self.id: value}})
            with open(self.dvc.params_file_path / self.dvc.params_file, "w") as json_file:
                json.dump(parameters, json_file)
        else:
            raise ValueError(f"Value has to be a dictionary but found {type(value)} instead!")

    @property
    def _dvc_file(self) -> dict:
        """Load ALL parameters from dvc.dvc_file"""
        try:
            with open(self.dvc.dvc_file) as json_file:
                return yaml.safe_load(json_file)
        except FileNotFoundError:
            log.debug(f"Could not load dvc config from {self.dvc.dvc_file}!")
        return {}

    @property
    def _dvc_stages(self) -> dict:
        """Load all stages from dvc.dvc_file"""
        return self._dvc_file['stages']

    @property
    def _dvc_stage(self) -> dict:
        """Load the current stage from dvc.dvc_file"""
        try:
            return self._dvc_stages[f"{self.name}_{self.id}"]
        except KeyError:
            return {}

    def _get_obj_by_id(self, id_: int):
        """

        Parameters
        ----------
        id_: int
            Primary key

        Returns
        -------

        DVCOp:
            Returns a new instance of a DVCOp with the correct id

        """
        obj = self.__class__()
        obj.parameters = self.all_parameters[self.name][str(id_)]  # need to convert int to str

        return obj

    def query_obj(self, filter_: Union[int, dict]) -> Union[DVCOp, List[DVCOp]]:
        """Get a class instance with all the available information attached

        Returns
        --------
        List[DVC_Op] : The instantiated class having self.parameters, self.id_ and potentially all post run parameters
                    set, so that it can be used

        Notes
        -----
        Most of the information will be in
            - self.id_
            - self.parameters
            - self.post_run_params
        """

        if isinstance(filter_, int):
            return self._get_obj_by_id(filter_)
        else:
            objs = []

            def filter_parameters() -> int:
                obj_id = -1
                for key, value in filter_.items():
                    if self.all_parameters[self.name][id_][key] == value:
                        obj_id = id_
                    else:
                        return -1
                return obj_id

            ids = []
            for id_ in self.all_parameters[self.name]:
                ids.append(filter_parameters())

            for id_ in ids:
                if id_ == -1:
                    continue
                objs.append(self._get_obj_by_id(id_))

            return objs

    def _write_dvc(self, force=False, exec_: bool = False, always_changed: bool = False, slurm: bool = False):
        """Write the DVC file using run.

        If it already exists it'll tell you that the stage is already persistent and has been run before.
        Otherwise it'll run the stage for you.

        Parameters
        ----------
        force: bool, default = False
            Force DVC to rerun this stage, even if the parameters haven't changed!
        exec_: bool, default = False
            if False, only write the stage to the dvc.yaml and run later. Otherwise the stage and ALL dependencies
            will be executed!
        always_changed: bool, default = False
            Tell DVC to always rerun this stage, e.g. for non-deterministic stages or for testing
        slurm: bool, default = False
            Use SLURM to run DVC stages on a Cluster.
            TODO add the important attributes
                add appropiate names
                make sure, that everything uses slurm, because otherwise
                you run stuff on the head node!

        Notes
        -----
        If the dependencies for a stage change this function won't necessarily tell you.
        Use 'dvc status' to check, if the stage needs to be rerun.
        """
        # TODO for multi use have some method that updates an existing stage rather than creating a new one
        #   maybe have an argument id_ and if that is given, that specific id will be overwritten
        # Also consider having multi_use as an argument in the __call__ method, so ideally you never need to bother
        # with id_, because if multi use is disabled, you can always assume id_ = 0

        script = ['dvc', 'run', '-n', self.stage_name]

        script += self.files.get_dvc_arguments()

        if force:
            script.append("--force")
            log.warning("Overwriting existing configuration!")
            # TODO check these logs!
        #
        if not exec_:
            script.append("--no-exec")
        else:
            log.warning("You will not be able to see the stdout/stderr of the process in real time!")
        #
        if always_changed:
            script.append("--always-changed")
        #
        if slurm:
            log.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            log.warning("Make sure, that every stage uses SLURM! If a stage does not have SLURM enabled, the command "
                        "will be run on the HEAD NODE! Check the dvc.yaml file before running! There are no checks"
                        "implemented to test, that only SRUN is in use!")
            log.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

            script.append('srun')
            script.append('-n')
            script.append(f"{self.slurm_config.n}")
        #
        script.append(f'python -c "from {self.module} import {self.name}; '
                      f'{self.name}().run_dvc(id_={self.id})"')
        log.debug(f"running script: {' '.join([str(x) for x in script])}")

        process = subprocess.run(script, shell=True, capture_output=True)
        if len(process.stdout) > 0:
            log.info(process.stdout.decode())
        if len(process.stderr) > 0:
            log.warning(process.stderr.decode())

    @property
    def files(self):

        if self._json_file is not None:
            json_file = self.dvc.outs_path / f"{self.id}_{self._json_file}"
        else:
            json_file = None

        files = Files(
            deps=[self.dvc.deps_path / f"{self.id}_{dep}" for dep in self.dvc.deps],
            outs=[self.dvc.outs_path / f"{self.id}_{out}" for out in self.dvc.outs],
            outs_no_cache=[self.dvc.outs_no_cache_path / f"{self.id}_{out}" for out in self.dvc.outs_no_cache],
            outs_persistent=[self.dvc.outs_persistent_path / f"{self.id}_{out}" for out in self.dvc.outs_persistent],
            params=[self.dvc.params_path / f"{self.id}_{param}" for param in self.dvc.params],
            metrics=[self.dvc.metrics_path / f"{self.id}_{metric}" for metric in self.dvc.metrics],
            metrics_no_cache=[self.dvc.metrics_no_cache_path / f"{self.id}_{metric}" for metric in
                              self.dvc.metrics_no_cache],
            plots=[self.dvc.plots_path / f"{self.id}_{plot}" for plot in self.dvc.plots],
            plots_no_cache=[self.dvc.plots_no_cache_path / f"{self.id}_{plot}" for plot in self.dvc.plots_no_cache],
            json_file=json_file
        )
        return files

    @property
    def results(self) -> dict:
        with open(self.files.json_file) as f:
            file = json.load(f)
        return file

    @results.setter
    def results(self, value):
        # TODO maybe make if self.files.json_file?!
        with open(self.files.json_file, "w") as f:
            json.dump(value, f)