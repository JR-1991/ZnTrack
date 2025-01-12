import re
from abc import ABC, abstractmethod
from functools import partial
from typing import Callable

from zntrack import utils
from zntrack.core.dvcgraph import filter_ZnTrackOption


class MetaData(ABC):
    """Base class for implementing MetaData decorators

    Attributes
    ----------
    name_of_metric: str
        A string that is unique for this metadata, it can not share the same startswith
        with any other metadata, e.g. "timeit" and "timeit_advanced" is not allowed!
    """

    name_of_metric: str

    def __init__(self, func: Callable):
        """Get the decorated function

        The MetaData decorator does not take arguments!
        @MetaData() does not work, use @MetaData or implement
        a version that supports both!

        Parameters
        ----------
        func
        """
        self.func: Callable = func
        self.func_name = self.func.__name__

    @abstractmethod
    def __call__(self, cls, *args, **kwargs):
        """Actual decorator"""
        raise NotImplementedError

    def __get__(self, instance, owner):
        """Converting decorator into descriptor

        tl;dr

        when using the decorator the instance of the decorated class
        is not available and is not passed correctly

        See the following answer for a full explanation why this is required
        https://stackoverflow.com/questions/30104047/how-can-i-decorate-an-instance-method-with-a-decorator-class
        """

        return partial(self.__call__, instance)

    def save_metadata(self, cls, value):
        """Save metadata to the class dict

        Will save the metadata as func_name:metric_name dictionary entry.
        If the func was called multiple times it will increment automatically by
        func_name_<#>:metric_name

        Parameters
        ----------
        cls: the class that has the cls.metadata ZnTrackOption
        value:
            Any value that should be saved

        Raises
        ------
        DescriptorMissing:
            If the Node does not contain a <zn.metadata> descriptor
        """

        try:
            metadata_attr, metadata = next(
                iter(
                    filter_ZnTrackOption(
                        data=cls._descriptor_list,
                        cls=cls,
                        zn_type=utils.ZnTypes.METADATA,
                        allow_none=True,
                    ).items()
                )
            )
        except StopIteration as error:
            raise utils.exceptions.DescriptorMissing(
                "Could not find a metadata descriptor. Please add zn.metadata()!"
            ) from error
        if metadata is None:
            metadata = {}

        pattern = re.compile(rf"{self.func_name}(_[1-9]+)?:{self.name_of_metric}")

        number_already_collected = len(list(filter(pattern.match, metadata)))

        if number_already_collected == 0:
            metadata_name = f"{self.func_name}:{self.name_of_metric}"
        else:
            metadata_name = (
                f"{self.func_name}_{number_already_collected}:{self.name_of_metric}"
            )
        metadata[metadata_name] = value
        setattr(cls, metadata_attr, metadata)
