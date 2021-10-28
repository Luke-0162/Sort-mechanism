from typing import Any

from markdown.extensions import Extension

from .control import ControlPattern
from .preproc import Preprocessor
from .postproc import Postprocessor

__all__ = ["makeTaipyExtension"]


class TaipyExtension(Extension):
    def extendMarkdown(self, md):
        md.registerExtension(self)
        md.preprocessors.add("taipy", Preprocessor(md), "_begin")
        ControlPattern.extendMarkdown(md)
        md.treeprocessors.register(Postprocessor(md), "taipy", 200)


def makeTaipyExtension(*args: Any, **kwargs: Any) -> Extension:
    return TaipyExtension(*args, **kwargs)
