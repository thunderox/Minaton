#! /usr/bin/env python
# encoding: utf-8
# WARNING! Do not edit! http://waf.googlecode.com/git/docs/wafbook/single.html#_obtaining_the_waf_file

try:
	from xml.sax import make_parser
	from xml.sax.handler import ContentHandler
except ImportError:
	has_xml=False
	ContentHandler=object
else:
	has_xml=True
import os,sys
from waflib.Tools import cxx
from waflib import Task,Utils,Options,Errors,Context
from waflib.TaskGen import feature,after_method,extension
from waflib.Configure import conf
from waflib import Logs
MOC_H=['.h','.hpp','.hxx','.hh']
EXT_RCC=['.qrc']
EXT_UI=['.ui']
EXT_QT5=['.cpp','.cc','.cxx','.C']
QT5_LIBS='''
qtmain
Qt5Bluetooth
Qt5CLucene
Qt5Concurrent
Qt5Core
Qt5DBus
Qt5Declarative
Qt5DesignerComponents
Qt5Designer
Qt5Gui
Qt5Help
Qt5MultimediaQuick_p
Qt5Multimedia
Qt5MultimediaWidgets
Qt5Network
Qt5Nfc
Qt5OpenGL
Qt5Positioning
Qt5PrintSupport
Qt5Qml
Qt5QuickParticles
Qt5Quick
Qt5QuickTest
Qt5Script
Qt5ScriptTools
Qt5Sensors
Qt5SerialPort
Qt5Sql
Qt5Svg
Qt5Test
Qt5WebKit
Qt5WebKitWidgets
Qt5Widgets
Qt5WinExtras
Qt5X11Extras
Qt5XmlPatterns
Qt5Xml'''
class qxx(Task.classes['cxx']):
	def __init__(self,*k,**kw):
		Task.Task.__init__(self,*k,**kw)
		self.moc_done=0
	def runnable_status(self):
		if self.moc_done:
			return Task.Task.runnable_status(self)
		else:
			for t in self.run_after:
				if not t.hasrun:
					return Task.ASK_LATER
			self.add_moc_tasks()
			return Task.Task.runnable_status(self)
	def create_moc_task(self,h_node,m_node):
		try:
			moc_cache=self.generator.bld.moc_cache
		except AttributeError:
			moc_cache=self.generator.bld.moc_cache={}
		try:
			return moc_cache[h_node]
		except KeyError:
			tsk=moc_cache[h_node]=Task.classes['moc'](env=self.env,generator=self.generator)
			tsk.set_inputs(h_node)
			tsk.set_outputs(m_node)
			if self.generator:
				self.generator.tasks.append(tsk)
			gen=self.generator.bld.producer
			gen.outstanding.insert(0,tsk)
			gen.total+=1
			return tsk
		else:
			delattr(self,'cache_sig')
	def moc_h_ext(self):
		try:
			ext=Options.options.qt_header_ext.split()
		except AttributeError:
			pass
		if not ext:
			ext=MOC_H
		return ext
	def add_moc_tasks(self):
		node=self.inputs[0]
		bld=self.generator.bld
		try:
			self.signature()
		except KeyError:
			pass
		else:
			delattr(self,'cache_sig')
		include_nodes=[node.parent]+self.generator.includes_nodes
		moctasks=[]
		mocfiles=set([])
		for d in bld.raw_deps.get(self.uid(),[]):
			if not d.endswith('.moc'):
				continue
			if d in mocfiles:
				continue
			mocfiles.add(d)
			h_node=None
			base2=d[:-4]
			for x in include_nodes:
				for e in self.moc_h_ext():
					h_node=x.find_node(base2+e)
					if h_node:
						break
				if h_node:
					m_node=h_node.change_ext('.moc')
					break
			else:
				for k in EXT_QT5:
					if base2.endswith(k):
						for x in include_nodes:
							h_node=x.find_node(base2)
							if h_node:
								break
						if h_node:
							m_node=h_node.change_ext(k+'.moc')
							break
			if not h_node:
				raise Errors.WafError('No source found for %r which is a moc file'%d)
			task=self.create_moc_task(h_node,m_node)
			moctasks.append(task)
		self.run_after.update(set(moctasks))
		self.moc_done=1
class trans_update(Task.Task):
	run_str='${QT_LUPDATE} ${SRC} -ts ${TGT}'
	color='BLUE'
Task.update_outputs(trans_update)
class XMLHandler(ContentHandler):
	def __init__(self):
		self.buf=[]
		self.files=[]
	def startElement(self,name,attrs):
		if name=='file':
			self.buf=[]
	def endElement(self,name):
		if name=='file':
			self.files.append(str(''.join(self.buf)))
	def characters(self,cars):
		self.buf.append(cars)
@extension(*EXT_RCC)
def create_rcc_task(self,node):
	rcnode=node.change_ext('_rc.cpp')
	self.create_task('rcc',node,rcnode)
	cpptask=self.create_task('cxx',rcnode,rcnode.change_ext('.o'))
	try:
		self.compiled_tasks.append(cpptask)
	except AttributeError:
		self.compiled_tasks=[cpptask]
	return cpptask
@extension(*EXT_UI)
def create_uic_task(self,node):
	uictask=self.create_task('ui5',node)
	uictask.outputs=[self.path.find_or_declare(self.env['ui_PATTERN']%node.name[:-3])]
@extension('.ts')
def add_lang(self,node):
	self.lang=self.to_list(getattr(self,'lang',[]))+[node]
@feature('qt5')
@after_method('apply_link')
def apply_qt5(self):
	if getattr(self,'lang',None):
		qmtasks=[]
		for x in self.to_list(self.lang):
			if isinstance(x,str):
				x=self.path.find_resource(x+'.ts')
			qmtasks.append(self.create_task('ts2qm',x,x.change_ext('.qm')))
		if getattr(self,'update',None)and Options.options.trans_qt5:
			cxxnodes=[a.inputs[0]for a in self.compiled_tasks]+[a.inputs[0]for a in self.tasks if getattr(a,'inputs',None)and a.inputs[0].name.endswith('.ui')]
			for x in qmtasks:
				self.create_task('trans_update',cxxnodes,x.inputs)
		if getattr(self,'langname',None):
			qmnodes=[x.outputs[0]for x in qmtasks]
			rcnode=self.langname
			if isinstance(rcnode,str):
				rcnode=self.path.find_or_declare(rcnode+'.qrc')
			t=self.create_task('qm2rcc',qmnodes,rcnode)
			k=create_rcc_task(self,t.outputs[0])
			self.link_task.inputs.append(k.outputs[0])
	lst=[]
	for flag in self.to_list(self.env['CXXFLAGS']):
		if len(flag)<2:continue
		f=flag[0:2]
		if f in('-D','-I','/D','/I'):
			if(f[0]=='/'):
				lst.append('-'+flag[1:])
			else:
				lst.append(flag)
	self.env.append_value('MOC_FLAGS',lst)
@extension(*EXT_QT5)
def cxx_hook(self,node):
	return self.create_compiled_task('qxx',node)
class rcc(Task.Task):
	color='BLUE'
	run_str='${QT_RCC} -name ${tsk.rcname()} ${SRC[0].abspath()} ${RCC_ST} -o ${TGT}'
	ext_out=['.h']
	def rcname(self):
		return os.path.splitext(self.inputs[0].name)[0]
	def scan(self):
		if not has_xml:
			Logs.error('no xml support was found, the rcc dependencies will be incomplete!')
			return([],[])
		parser=make_parser()
		curHandler=XMLHandler()
		parser.setContentHandler(curHandler)
		fi=open(self.inputs[0].abspath(),'r')
		try:
			parser.parse(fi)
		finally:
			fi.close()
		nodes=[]
		names=[]
		root=self.inputs[0].parent
		for x in curHandler.files:
			nd=root.find_resource(x)
			if nd:nodes.append(nd)
			else:names.append(x)
		return(nodes,names)
class moc(Task.Task):
	color='BLUE'
	run_str='${QT_MOC} ${MOC_FLAGS} ${MOCCPPPATH_ST:INCPATHS} ${MOCDEFINES_ST:DEFINES} ${SRC} ${MOC_ST} ${TGT}'
class ui5(Task.Task):
	color='BLUE'
	run_str='${QT_UIC} ${SRC} -o ${TGT}'
	ext_out=['.h']
class ts2qm(Task.Task):
	color='BLUE'
	run_str='${QT_LRELEASE} ${QT_LRELEASE_FLAGS} ${SRC} -qm ${TGT}'
class qm2rcc(Task.Task):
	color='BLUE'
	after='ts2qm'
	def run(self):
		txt='\n'.join(['<file>%s</file>'%k.path_from(self.outputs[0].parent)for k in self.inputs])
		code='<!DOCTYPE RCC><RCC version="1.0">\n<qresource>\n%s\n</qresource>\n</RCC>'%txt
		self.outputs[0].write(code)
def configure(self):
	self.find_qt5_binaries()
	self.set_qt5_libs_to_check()
	self.set_qt5_defines()
	self.find_qt5_libraries()
	self.add_qt5_rpath()
	self.simplify_qt5_libs()
@conf
def find_qt5_binaries(self):
	env=self.env
	opt=Options.options
	qtdir=getattr(opt,'qtdir','')
	qtbin=getattr(opt,'qtbin','')
	paths=[]
	if qtdir:
		qtbin=os.path.join(qtdir,'bin')
	if not qtdir:
		qtdir=os.environ.get('QT5_ROOT','')
		qtbin=os.environ.get('QT5_BIN',None)or os.path.join(qtdir,'bin')
	if qtbin:
		paths=[qtbin]
	if not qtdir:
		paths=os.environ.get('PATH','').split(os.pathsep)
		paths.append('/usr/share/qt5/bin/')
		try:
			lst=Utils.listdir('/usr/local/Trolltech/')
		except OSError:
			pass
		else:
			if lst:
				lst.sort()
				lst.reverse()
				qtdir='/usr/local/Trolltech/%s/'%lst[0]
				qtbin=os.path.join(qtdir,'bin')
				paths.append(qtbin)
	cand=None
	prev_ver=['5','0','0']
	for qmk in('qmake-qt5','qmake5','qmake'):
		try:
			qmake=self.find_program(qmk,path_list=paths)
		except self.errors.ConfigurationError:
			pass
		else:
			try:
				version=self.cmd_and_log(qmake+['-query','QT_VERSION']).strip()
			except self.errors.WafError:
				pass
			else:
				if version:
					new_ver=version.split('.')
					if new_ver>prev_ver:
						cand=qmake
						prev_ver=new_ver
	if cand:
		self.env.QMAKE=cand
	else:
		self.fatal('Could not find qmake for qt5')
	qtbin=self.cmd_and_log(self.env.QMAKE+['-query','QT_INSTALL_BINS']).strip()+os.sep
	def find_bin(lst,var):
		if var in env:
			return
		for f in lst:
			try:
				ret=self.find_program(f,path_list=paths)
			except self.errors.ConfigurationError:
				pass
			else:
				env[var]=ret
				break
	find_bin(['uic-qt5','uic'],'QT_UIC')
	if not env.QT_UIC:
		self.fatal('cannot find the uic compiler for qt5')
	self.start_msg('Checking for uic version')
	uicver=self.cmd_and_log(env.QT_UIC+["-version"],output=Context.BOTH)
	uicver=''.join(uicver).strip()
	uicver=uicver.replace('Qt User Interface Compiler ','').replace('User Interface Compiler for Qt','')
	self.end_msg(uicver)
	if uicver.find(' 3.')!=-1 or uicver.find(' 4.')!=-1:
		self.fatal('this uic compiler is for qt3 or qt5, add uic for qt5 to your path')
	find_bin(['moc-qt5','moc'],'QT_MOC')
	find_bin(['rcc-qt5','rcc'],'QT_RCC')
	find_bin(['lrelease-qt5','lrelease'],'QT_LRELEASE')
	find_bin(['lupdate-qt5','lupdate'],'QT_LUPDATE')
	env['UIC_ST']='%s -o %s'
	env['MOC_ST']='-o'
	env['ui_PATTERN']='ui_%s.h'
	env['QT_LRELEASE_FLAGS']=['-silent']
	env.MOCCPPPATH_ST='-I%s'
	env.MOCDEFINES_ST='-D%s'
@conf
def find_qt5_libraries(self):
	qtlibs=getattr(Options.options,'qtlibs',None)or os.environ.get("QT5_LIBDIR",None)
	if not qtlibs:
		try:
			qtlibs=self.cmd_and_log(self.env.QMAKE+['-query','QT_INSTALL_LIBS']).strip()
		except Errors.WafError:
			qtdir=self.cmd_and_log(self.env.QMAKE+['-query','QT_INSTALL_PREFIX']).strip()+os.sep
			qtlibs=os.path.join(qtdir,'lib')
	self.msg('Found the Qt5 libraries in',qtlibs)
	qtincludes=os.environ.get("QT5_INCLUDES",None)or self.cmd_and_log(self.env.QMAKE+['-query','QT_INSTALL_HEADERS']).strip()
	env=self.env
	if not'PKG_CONFIG_PATH'in os.environ:
		os.environ['PKG_CONFIG_PATH']='%s:%s/pkgconfig:/usr/lib/qt5/lib/pkgconfig:/opt/qt5/lib/pkgconfig:/usr/lib/qt5/lib:/opt/qt5/lib'%(qtlibs,qtlibs)
	try:
		if os.environ.get("QT5_XCOMPILE",None):
			raise self.errors.ConfigurationError()
		self.check_cfg(atleast_pkgconfig_version='0.1')
	except self.errors.ConfigurationError:
		for i in self.qt5_vars:
			uselib=i.upper()
			if Utils.unversioned_sys_platform()=="darwin":
				frameworkName=i+".framework"
				qtDynamicLib=os.path.join(qtlibs,frameworkName,i)
				if os.path.exists(qtDynamicLib):
					env.append_unique('FRAMEWORK_'+uselib,i)
					self.msg('Checking for %s'%i,qtDynamicLib,'GREEN')
				else:
					self.msg('Checking for %s'%i,False,'YELLOW')
				env.append_unique('INCLUDES_'+uselib,os.path.join(qtlibs,frameworkName,'Headers'))
			elif env.DEST_OS!="win32":
				qtDynamicLib=os.path.join(qtlibs,"lib"+i+".so")
				qtStaticLib=os.path.join(qtlibs,"lib"+i+".a")
				if os.path.exists(qtDynamicLib):
					env.append_unique('LIB_'+uselib,i)
					self.msg('Checking for %s'%i,qtDynamicLib,'GREEN')
				elif os.path.exists(qtStaticLib):
					env.append_unique('LIB_'+uselib,i)
					self.msg('Checking for %s'%i,qtStaticLib,'GREEN')
				else:
					self.msg('Checking for %s'%i,False,'YELLOW')
				env.append_unique('LIBPATH_'+uselib,qtlibs)
				env.append_unique('INCLUDES_'+uselib,qtincludes)
				env.append_unique('INCLUDES_'+uselib,os.path.join(qtincludes,i))
			else:
				for k in("lib%s.a","lib%s5.a","%s.lib","%s5.lib"):
					lib=os.path.join(qtlibs,k%i)
					if os.path.exists(lib):
						env.append_unique('LIB_'+uselib,i+k[k.find("%s")+2:k.find('.')])
						self.msg('Checking for %s'%i,lib,'GREEN')
						break
				else:
					self.msg('Checking for %s'%i,False,'YELLOW')
				env.append_unique('LIBPATH_'+uselib,qtlibs)
				env.append_unique('INCLUDES_'+uselib,qtincludes)
				env.append_unique('INCLUDES_'+uselib,os.path.join(qtincludes,i))
				uselib=i.upper()+"_debug"
				for k in("lib%sd.a","lib%sd5.a","%sd.lib","%sd5.lib"):
					lib=os.path.join(qtlibs,k%i)
					if os.path.exists(lib):
						env.append_unique('LIB_'+uselib,i+k[k.find("%s")+2:k.find('.')])
						self.msg('Checking for %s'%i,lib,'GREEN')
						break
				else:
					self.msg('Checking for %s'%i,False,'YELLOW')
				env.append_unique('LIBPATH_'+uselib,qtlibs)
				env.append_unique('INCLUDES_'+uselib,qtincludes)
				env.append_unique('INCLUDES_'+uselib,os.path.join(qtincludes,i))
	else:
		for i in self.qt5_vars_debug+self.qt5_vars:
			self.check_cfg(package=i,args='--cflags --libs',mandatory=False)
@conf
def simplify_qt5_libs(self):
	env=self.env
	def process_lib(vars_,coreval):
		for d in vars_:
			var=d.upper()
			if var=='QTCORE':
				continue
			value=env['LIBPATH_'+var]
			if value:
				core=env[coreval]
				accu=[]
				for lib in value:
					if lib in core:
						continue
					accu.append(lib)
				env['LIBPATH_'+var]=accu
	process_lib(self.qt5_vars,'LIBPATH_QTCORE')
	process_lib(self.qt5_vars_debug,'LIBPATH_QTCORE_DEBUG')
@conf
def add_qt5_rpath(self):
	env=self.env
	if getattr(Options.options,'want_rpath',False):
		def process_rpath(vars_,coreval):
			for d in vars_:
				var=d.upper()
				value=env['LIBPATH_'+var]
				if value:
					core=env[coreval]
					accu=[]
					for lib in value:
						if var!='QTCORE':
							if lib in core:
								continue
						accu.append('-Wl,--rpath='+lib)
					env['RPATH_'+var]=accu
		process_rpath(self.qt5_vars,'LIBPATH_QTCORE')
		process_rpath(self.qt5_vars_debug,'LIBPATH_QTCORE_DEBUG')
@conf
def set_qt5_libs_to_check(self):
	if not hasattr(self,'qt5_vars'):
		self.qt5_vars=QT5_LIBS
	self.qt5_vars=Utils.to_list(self.qt5_vars)
	if not hasattr(self,'qt5_vars_debug'):
		self.qt5_vars_debug=[a+'_debug'for a in self.qt5_vars]
	self.qt5_vars_debug=Utils.to_list(self.qt5_vars_debug)
@conf
def set_qt5_defines(self):
	if sys.platform!='win32':
		return
	for x in self.qt5_vars:
		y=x[2:].upper()
		self.env.append_unique('DEFINES_%s'%x.upper(),'QT_%s_LIB'%y)
		self.env.append_unique('DEFINES_%s_DEBUG'%x.upper(),'QT_%s_LIB'%y)
def options(opt):
	opt.add_option('--want-rpath',action='store_true',default=False,dest='want_rpath',help='enable the rpath for qt libraries')
	opt.add_option('--header-ext',type='string',default='',help='header extension for moc files',dest='qt_header_ext')
	for i in'qtdir qtbin qtlibs'.split():
		opt.add_option('--'+i,type='string',default='',dest=i)
	opt.add_option('--translate',action="store_true",help="collect translation strings",dest="trans_qt5",default=False)
