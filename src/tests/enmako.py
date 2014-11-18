#!/usr/bin/env python

import os
import io

import argh
from mako.template import Template
from mako.exceptions import text_error_template


def render_mako_template_to(
        template, outpath, subsd, only_update=False, cwd=None,
        prev_subsd=None, create_dest_dirs=False, logger=None,
        pass_warn_string=True, **kwargs):
    """
    template: either string of path or file like obj.

    Beware of the only_update option, it pays no attention to
    an updated subsd.

    pass_warn_string: defult True
    if True or instance of basetring:
    an extra vairable named '_warning_in_the_generated_file_not_to_edit'
    is passed with a preset (True) or string (basestring) warning not to
    directly edit the generated file.
    """
    if cwd:
        template = os.path.join(cwd, template)
        outpath = os.path.join(cwd, outpath)
    outdir = os.path.dirname(outpath) or '.'  # avoid ''

    if not os.path.exists(outdir):
        if create_dest_dirs:
            make_dirs(outdir, logger=logger)
        else:
            raise IOError(
                "Dest. dir. non-existent: {}".format(outdir))

    if only_update:
        if not missing_or_other_newer(outpath, template):
            if (prev_subsd is None) or (prev_subsd == subsd):
                if logger:
                    msg = ("Did not re-render {}. " +
                           "(destination newer + same dict)")
                    logger.info(msg.format(template))
                return

    msg = None
    if pass_warn_string is True:
        subsd[u'_warning_in_the_generated_file_not_to_edit'] = (
            u"DO NOT EDIT THIS FILE! (Generated from template: {} using"
            " Mako python templating engine)"
        ).format(os.path.basename(template))
    elif isinstance(pass_warn_string, basestring):
        subsd[u'_warning_in_the_generated_file_not_to_edit'] =\
            pass_warn_string

    if hasattr(template, 'read'):
        # set in-file handle to provided template
        ifh = template
    else:
        # Assume template is a string of the path to the template
        ifh = io.open(template, 'r', encoding='utf-8')

    template_str = ifh.read()

    kwargs_Template = {'input_encoding': 'utf-8', 'output_encoding': 'utf-8'}
    kwargs_Template.update(kwargs)
    with io.open(outpath, 'w', encoding='utf-8') as ofh:
        from mako.template import Template
        from mako.exceptions import text_error_template
        try:
            rendered = Template(
                template_str, **kwargs_Template).render_unicode(**subsd)
        except:
            if logger:
                logger.error(text_error_template().render_unicode())
            else:
                print(text_error_template().render_unicode())
            raise
        if logger:
            logger.info("Rendering '{}' to '{}'...".format(
                ifh.name, outpath))
        ofh.write(rendered)
    return outpath


def enmako(template_path, gen_subsd_eval=None, shell_cmd_subs=None,
           json_subs=None, pickle_subs=None, outpath=None):
    """
    User provides a template file path, e.g. `index.html.mako`
    and either a python expression (gen_subsd_eval) which evaluates to a dict
    e.g. '{"title": "Welcome"}'
    or a shell command (shell_cmd_subs) which outputs lines of form:
    title=Welcome. If outpath is not given, template_path will be stripped
    from trailing `.mako` (required in that case)

    Note: json does not support integer keys in dicts
    """
    if outpath is None:
        assert template_path.endswith('.mako')
        outpath = template_path[:-5]
    subsd = {}
    if gen_subsd_eval:
        subsd.update(eval(gen_subsd_eval))
    if json_subs:
        import json
        subsd.update(json.load(open(json_subs, 'rt')))
    if pickle_subs:
        try:
            import cPickle as pickle
        except ImportError:
            import pickle
        subsd.update(pickle.load(open(pickle_subs, 'rt')))
    if shell_cmd_subs:
        import subprocess
        outp = subprocess.check_output(shell_cmd_subs.split())
        subsd.update(dict([x.split('=') for x in outp.split('\n')[:-1]]))
    render_mako_template_to(template_path, outpath, subsd)

if __name__ == '__main__':
    argh.dispatch_command(enmako)
