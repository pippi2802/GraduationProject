package edu.penn.rtg.schedulingapp.input.treeGUI.translator;

import java.util.HashMap;
import java.util.Map;
import java.util.Vector;

import edu.penn.rtg.schedulingapp.ResourceModelList;
import edu.penn.rtg.schedulingapp.TaskList;
import edu.penn.rtg.schedulingapp.TreeComponent;

public class SchedulingTreeRoot2ComponentRoot {

	//private Component rootMPR2;
	private TreeComponent rootSchedulingTree;
	

	public static edu.penn.rtg.csa.mpr2.Component transfer2MPR2Root(TreeComponent rootSchedulingTree, edu.penn.rtg.csa.mpr2.Component parentComponentMPR2){
		if(rootSchedulingTree == null){
			System.err.println("rootSchedulingTree is null!");
			return null;
		}
	
		edu.penn.rtg.csa.mpr2.Component rootMPR2 = new edu.penn.rtg.csa.mpr2.Component();
		rootMPR2.setComponentFilename("GUI-input.xml");
		rootMPR2.setComponentName(rootSchedulingTree.getCompName());
		rootMPR2.setRoot(rootSchedulingTree.isRoot());
		rootMPR2.setParentComponent(parentComponentMPR2);
		rootMPR2.setSchedulingPolicy(rootSchedulingTree.getSchCom().getAlgorithm());
		edu.penn.rtg.csa.mpr2.MPR2 mpr2Interface = new edu.penn.rtg.csa.mpr2.MPR2();
		if(rootSchedulingTree.getSchCom().getPeriod() != 0){
			mpr2Interface.setPi(rootSchedulingTree.getSchCom().getPeriod());
		}else{
			if(rootSchedulingTree.getSchCom().getMaxPeriod() == rootSchedulingTree.getSchCom().getMinPeriod()){
				mpr2Interface.setPi(rootSchedulingTree.getSchCom().getMaxPeriod());
			}else{
				System.err.println("Error! MPR2 not support a range of interface periods now!");
			}	
		}
		
		rootMPR2.setmPR2Interface(mpr2Interface);
		rootMPR2.setInterfaceComputed(false);
		
		edu.penn.rtg.schedulingapp.TaskList taskList_TreeComponent = rootSchedulingTree.getTaskList();
		Vector<edu.penn.rtg.schedulingapp.TreeComponent> children_TreeComponent = rootSchedulingTree.getAllChildren();
		Vector<edu.penn.rtg.csa.mpr2.Task> taskset_mpr2 = new Vector<edu.penn.rtg.csa.mpr2.Task>();
		for(edu.penn.rtg.schedulingapp.Task task_TreeComponent : taskList_TreeComponent.getTasks()){
			edu.penn.rtg.csa.mpr2.Task task_mpr2 = new edu.penn.rtg.csa.mpr2.Task(); 
			task_mpr2.setName(task_TreeComponent.getName());
			task_mpr2.setPeriod(task_TreeComponent.getPeriod());
			task_mpr2.setExe(task_TreeComponent.getExecution());
			task_mpr2.setDeadline(task_TreeComponent.getDeadline());
			task_mpr2.setDelta_rel(task_TreeComponent.getDelta_rel());
			task_mpr2.setDelta_sch(task_TreeComponent.getDelta_sch());
			task_mpr2.setDelta_cxs(task_TreeComponent.getDelta_cxs());
			task_mpr2.setDelta_crpmd(task_TreeComponent.getDelta_crpmd());
			taskset_mpr2.add(task_mpr2);
		}
		rootMPR2.setTaskset(taskset_mpr2);
		
		for(edu.penn.rtg.schedulingapp.TreeComponent treeComponent: children_TreeComponent){
			rootMPR2.addChildComponent(transfer2MPR2Root(treeComponent, rootMPR2));
		}
		
		return rootMPR2;
		
	}
	
	public static edu.penn.rtg.csa.dmpr.Component transfer2DMPRRoot(TreeComponent rootSchedulingTree, edu.penn.rtg.csa.dmpr.Component parentComponentDMPR){
		if(rootSchedulingTree == null){
			System.err.println("rootSchedulingTree is null!");
			return null;
		}
	
		edu.penn.rtg.csa.dmpr.Component rootDMPR = new edu.penn.rtg.csa.dmpr.Component();
		rootDMPR.setComponentFilename("GUI-input.xml");
		rootDMPR.setComponentName(rootSchedulingTree.getCompName());
		rootDMPR.setRoot(rootSchedulingTree.isRoot());
		rootDMPR.setParentComponent(parentComponentDMPR);
		rootDMPR.setSchedulingPolicy(rootSchedulingTree.getSchCom().getAlgorithm());
		edu.penn.rtg.csa.dmpr.DMPR dmprInterface = new edu.penn.rtg.csa.dmpr.DMPR();
		if(rootSchedulingTree.getSchCom().getPeriod() != 0){
			dmprInterface.setPi(rootSchedulingTree.getSchCom().getPeriod());
		}else{
			if(rootSchedulingTree.getSchCom().getMaxPeriod() == rootSchedulingTree.getSchCom().getMinPeriod()){
				dmprInterface.setPi(rootSchedulingTree.getSchCom().getMaxPeriod());
			}else{
				System.err.println("Error! MPR2 not support a range of interface periods now!");
			}	
		}
		rootDMPR.setdMPRInterface(dmprInterface);
		rootDMPR.setInterfaceComputed(false);
		
		edu.penn.rtg.schedulingapp.TaskList taskList_TreeComponent = rootSchedulingTree.getTaskList();
		Vector<edu.penn.rtg.schedulingapp.TreeComponent> children_TreeComponent = rootSchedulingTree.getAllChildren();
		Vector<edu.penn.rtg.csa.dmpr.Task> taskset_dmpr = new Vector<edu.penn.rtg.csa.dmpr.Task>();
		for(edu.penn.rtg.schedulingapp.Task task_TreeComponent : taskList_TreeComponent.getTasks()){
			edu.penn.rtg.csa.dmpr.Task task_dmpr = new edu.penn.rtg.csa.dmpr.Task(); 
			task_dmpr.setName(task_TreeComponent.getName());
			task_dmpr.setPeriod(task_TreeComponent.getPeriod());
			task_dmpr.setExe(task_TreeComponent.getExecution());
			task_dmpr.setDeadline(task_TreeComponent.getDeadline());
			task_dmpr.setDelta_rel(task_TreeComponent.getDelta_rel());
			task_dmpr.setDelta_sch(task_TreeComponent.getDelta_sch());
			task_dmpr.setDelta_cxs(task_TreeComponent.getDelta_cxs());
			task_dmpr.setDelta_crpmd(task_TreeComponent.getDelta_crpmd());
			taskset_dmpr.add(task_dmpr);
		}
		rootDMPR.setTaskset(taskset_dmpr);
		
		for(edu.penn.rtg.schedulingapp.TreeComponent treeComponent: children_TreeComponent){
			rootDMPR.addChildComponent(transfer2DMPRRoot(treeComponent, rootDMPR));
		}
		
		return rootDMPR;
		
	}
	

	public static edu.penn.rtg.csa.cadmpr.Component transfer2CADMPRRoot(TreeComponent rootSchedulingTree, edu.penn.rtg.csa.cadmpr.Component parentComponentCADMPR){
		if(rootSchedulingTree == null){
			System.err.println("rootSchedulingTree is null!");
			return null;
		}
	
		edu.penn.rtg.csa.cadmpr.Component rootCADMPR = new edu.penn.rtg.csa.cadmpr.Component();
		rootCADMPR.setComponentFilename("GUI-input.xml");
		rootCADMPR.setComponentName(rootSchedulingTree.getCompName());
		rootCADMPR.setRoot(rootSchedulingTree.isRoot());
		rootCADMPR.setParentComponent(parentComponentCADMPR);
		rootCADMPR.setSchedulingPolicy(rootSchedulingTree.getSchCom().getAlgorithm());
		edu.penn.rtg.csa.cadmpr.CADMPR cadmprInterface = new edu.penn.rtg.csa.cadmpr.CADMPR();
		if(rootSchedulingTree.getSchCom().getPeriod() != 0){
			cadmprInterface.setPi(rootSchedulingTree.getSchCom().getPeriod());
		}else{
			if(rootSchedulingTree.getSchCom().getMaxPeriod() == rootSchedulingTree.getSchCom().getMinPeriod()){
				cadmprInterface.setPi(rootSchedulingTree.getSchCom().getMaxPeriod());
			}else{
				System.err.println("Error! MPR2 not support a range of interface periods now!");
			}	
		}
		rootCADMPR.setCacheAwareMPRInterface(cadmprInterface);
		rootCADMPR.setInterfaceComputed(false);
		
		edu.penn.rtg.schedulingapp.TaskList taskList_TreeComponent = rootSchedulingTree.getTaskList();
		Vector<edu.penn.rtg.schedulingapp.TreeComponent> children_TreeComponent = rootSchedulingTree.getAllChildren();
		Vector<edu.penn.rtg.csa.cadmpr.Task> taskset_cadmpr = new Vector<edu.penn.rtg.csa.cadmpr.Task>();
		for(edu.penn.rtg.schedulingapp.Task task_TreeComponent : taskList_TreeComponent.getTasks()){
			edu.penn.rtg.csa.cadmpr.Task task_cadmpr = new edu.penn.rtg.csa.cadmpr.Task(); 
			task_cadmpr.setName(task_TreeComponent.getName());
			task_cadmpr.setPeriod(task_TreeComponent.getPeriod());
			task_cadmpr.setExe(task_TreeComponent.getExecution());
			task_cadmpr.setDeadline(task_TreeComponent.getDeadline());
			task_cadmpr.setDelta_rel(task_TreeComponent.getDelta_rel());
			task_cadmpr.setDelta_sch(task_TreeComponent.getDelta_sch());
			task_cadmpr.setDelta_cxs(task_TreeComponent.getDelta_cxs());
			task_cadmpr.setDelta_crpmd(task_TreeComponent.getDelta_crpmd());
			taskset_cadmpr.add(task_cadmpr);
		}
		rootCADMPR.setTaskset(taskset_cadmpr);
		
		for(edu.penn.rtg.schedulingapp.TreeComponent treeComponent: children_TreeComponent){
			rootCADMPR.addChildComponent(transfer2CADMPRRoot(treeComponent, rootCADMPR));
		}
		
		return rootCADMPR;
		
	}
	
	/**
	 * transfer componentMPR2 to treeComponent and all its children
	 * @param componentMPR2
	 * @param treeComponent
	 */
	public static void transfer2TreeComponent(edu.penn.rtg.csa.mpr2.Component componentMPR2, TreeComponent treeComponent){
	
//		TreeComponent treeComponent = new TreeComponent();
		Vector<TreeComponent> children = treeComponent.getChildren();
//		TaskList taskList = new TaskList();
		TaskList processedTaskList = new TaskList();
		ResourceModelList resourceList = new ResourceModelList();
		Map<TreeComponent, TaskList> childrenToTasks = new HashMap<TreeComponent, TaskList>(); //meng: unclear what it is used for. may add it after knowing its usage
		
		//recursively tranfer from MPR2 to TreeComponent
		for(edu.penn.rtg.csa.mpr2.Component childComponent : componentMPR2.getChildComponents()){
			TreeComponent child = treeComponent.findChildComponentByName(childComponent.getComponentName());
			transfer2TreeComponent(childComponent, child);
			
		}
		//set treeComponent's properties
//		for(edu.penn.rtg.csa.mpr2.Task fromTask : componentMPR2.getTaskset()){
//			edu.penn.rtg.schedulingapp.Task toTask = new edu.penn.rtg.schedulingapp.Task(fromTask.getName());
//			toTask.setPeriod(fromTask.getPeriod());
//			toTask.setExecution(fromTask.getExe());
//			toTask.setDeadline(fromTask.getDeadline());
//			toTask.setDelta_rel(fromTask.getDelta_rel());
//			toTask.setDelta_sch(fromTask.getDelta_sch());
//			toTask.setDelta_cxs(fromTask.getDelta_cxs());
//			toTask.setDelta_crpmd(fromTask.getDelta_crpmd());
//			taskList.addToList(toTask);
//		}
		for(edu.penn.rtg.csa.mpr2.Task fromTask : componentMPR2.getInterfaceTaskset()){
			edu.penn.rtg.schedulingapp.Task toTask = new edu.penn.rtg.schedulingapp.Task(fromTask.getName());
			toTask.setPeriod(fromTask.getPeriod());
			toTask.setExecution(fromTask.getExe());
			toTask.setDeadline(fromTask.getDeadline());
			toTask.setDelta_rel(fromTask.getDelta_rel());
			toTask.setDelta_sch(fromTask.getDelta_sch());
			toTask.setDelta_cxs(fromTask.getDelta_cxs());
			toTask.setDelta_crpmd(fromTask.getDelta_crpmd());
			processedTaskList.addToList(toTask);
		}
		edu.penn.rtg.csa.mpr2.MPR2 mPR2 = componentMPR2.getmPR2Interface();
		edu.penn.rtg.schedulingapp.ResourceModel resourceModel = 
				new edu.penn.rtg.schedulingapp.ResourceModel(mPR2.getPi(),mPR2.getTheta(), mPR2.getM_prime(),0,0,0);
		resourceModel.setType("MPR");
		resourceList.addToList(resourceModel);
//		treeComponent.getResourceModelList().addToList(resourceModel);
		
//		treeComponent.setCompName(componentMPR2.getComponentName());
//		treeComponent.getSchCom().setAlgorithm(componentMPR2.getSchedulingPolicy());
		treeComponent.setProcessed(true);
//		treeComponent.setParent(treeComponentParent);
//		treeComponent.setChildren(children);
//		treeComponent.setTaskList(taskList);
		treeComponent.setProcessedTaskList(processedTaskList);
		treeComponent.setResourceModelList(resourceList);
		
	}
	

	public static void transfer2TreeComponent(edu.penn.rtg.csa.dmpr.Component componentDMPR, TreeComponent treeComponent){
	
//		TreeComponent treeComponent = new TreeComponent();
		Vector<TreeComponent> children = treeComponent.getChildren();
//		TaskList taskList = new TaskList();
		TaskList processedTaskList = new TaskList();
		ResourceModelList resourceList = new ResourceModelList();
		Map<TreeComponent, TaskList> childrenToTasks = new HashMap<TreeComponent, TaskList>(); //meng: unclear what it is used for. may add it after knowing its usage
		
		//recursively tranfer from MPR2 to TreeComponent
		for(edu.penn.rtg.csa.dmpr.Component childComponent : componentDMPR.getChildComponents()){
			TreeComponent child = treeComponent.findChildComponentByName(childComponent.getComponentName());
			transfer2TreeComponent(childComponent, child);
		}
		//set treeComponent's properties
//		for(edu.penn.rtg.csa.mpr2.Task fromTask : componentMPR2.getTaskset()){
//			edu.penn.rtg.schedulingapp.Task toTask = new edu.penn.rtg.schedulingapp.Task(fromTask.getName());
//			toTask.setPeriod(fromTask.getPeriod());
//			toTask.setExecution(fromTask.getExe());
//			toTask.setDeadline(fromTask.getDeadline());
//			toTask.setDelta_rel(fromTask.getDelta_rel());
//			toTask.setDelta_sch(fromTask.getDelta_sch());
//			toTask.setDelta_cxs(fromTask.getDelta_cxs());
//			toTask.setDelta_crpmd(fromTask.getDelta_crpmd());
//			taskList.addToList(toTask);
//		}
		for(edu.penn.rtg.csa.dmpr.Task fromTask : componentDMPR.getInterfaceTaskset()){
			edu.penn.rtg.schedulingapp.Task toTask = new edu.penn.rtg.schedulingapp.Task(fromTask.getName());
			toTask.setPeriod(fromTask.getPeriod());
			toTask.setExecution(fromTask.getExe());
			toTask.setDeadline(fromTask.getDeadline());
			toTask.setDelta_rel(fromTask.getDelta_rel());
			toTask.setDelta_sch(fromTask.getDelta_sch());
			toTask.setDelta_cxs(fromTask.getDelta_cxs());
			toTask.setDelta_crpmd(fromTask.getDelta_crpmd());
			processedTaskList.addToList(toTask);
		}
		edu.penn.rtg.csa.dmpr.DMPR dMPR = componentDMPR.getdMPRInterface();
		double period_dmpr = dMPR.getPi();
		double theta_dmpr = 0;
		int m_prime_dmpr = 0;
		if(dMPR.getM_prime()*dMPR.getPi() == dMPR.getTheta()){
			theta_dmpr = 0;
			m_prime_dmpr = dMPR.getM_prime() + dMPR.getM_dedicatedCores();
		}else{
			theta_dmpr = dMPR.getTheta() - (dMPR.getM_prime()-1)*dMPR.getPi(); // partial VCPU's budget
			m_prime_dmpr = dMPR.getM_prime() - 1 + dMPR.getM_dedicatedCores(); 
		}
		edu.penn.rtg.schedulingapp.ResourceModel resourceModel = 
				new edu.penn.rtg.schedulingapp.ResourceModel(period_dmpr, theta_dmpr, m_prime_dmpr,0,0,0);
		resourceModel.setType("DMPR");
		resourceList.addToList(resourceModel);
//		treeComponent.getResourceModelList().addToList(resourceModel);
		
//		treeComponent.setCompName(componentMPR2.getComponentName());
//		treeComponent.getSchCom().setAlgorithm(componentMPR2.getSchedulingPolicy());
		treeComponent.setProcessed(true);
//		treeComponent.setParent(treeComponentParent);
//		treeComponent.setChildren(children);
//		treeComponent.setTaskList(taskList);
		treeComponent.setProcessedTaskList(processedTaskList);
		treeComponent.setResourceModelList(resourceList);
	}
	
	public static void transfer2TreeComponent(edu.penn.rtg.csa.cadmpr.Component componentCADMPR, String type ,TreeComponent treeComponent){
		
//		TreeComponent treeComponent = new TreeComponent();
		Vector<TreeComponent> children = treeComponent.getChildren();
//		TaskList taskList = new TaskList();
		TaskList processedTaskList = new TaskList();
		ResourceModelList resourceList = new ResourceModelList();
		Map<TreeComponent, TaskList> childrenToTasks = new HashMap<TreeComponent, TaskList>(); //meng: unclear what it is used for. may add it after knowing its usage
		
		//recursively tranfer from MPR2 to TreeComponent
		for(edu.penn.rtg.csa.cadmpr.Component childComponent : componentCADMPR.getChildComponents()){
			TreeComponent child = treeComponent.findChildComponentByName(childComponent.getComponentName());
			transfer2TreeComponent(childComponent, type, child);
		}
		//set treeComponent's properties
//		for(edu.penn.rtg.csa.mpr2.Task fromTask : componentMPR2.getTaskset()){
//			edu.penn.rtg.schedulingapp.Task toTask = new edu.penn.rtg.schedulingapp.Task(fromTask.getName());
//			toTask.setPeriod(fromTask.getPeriod());
//			toTask.setExecution(fromTask.getExe());
//			toTask.setDeadline(fromTask.getDeadline());
//			toTask.setDelta_rel(fromTask.getDelta_rel());
//			toTask.setDelta_sch(fromTask.getDelta_sch());
//			toTask.setDelta_cxs(fromTask.getDelta_cxs());
//			toTask.setDelta_crpmd(fromTask.getDelta_crpmd());
//			taskList.addToList(toTask);
//		}
		for(edu.penn.rtg.csa.cadmpr.Task fromTask : componentCADMPR.getInterfaceTaskset()){
			edu.penn.rtg.schedulingapp.Task toTask = new edu.penn.rtg.schedulingapp.Task(fromTask.getName());
			toTask.setPeriod(fromTask.getPeriod());
			toTask.setExecution(fromTask.getExe());
			toTask.setDeadline(fromTask.getDeadline());
			toTask.setDelta_rel(fromTask.getDelta_rel());
			toTask.setDelta_sch(fromTask.getDelta_sch());
			toTask.setDelta_cxs(fromTask.getDelta_cxs());
			toTask.setDelta_crpmd(fromTask.getDelta_crpmd());
			processedTaskList.addToList(toTask);
		}
		edu.penn.rtg.csa.cadmpr.CADMPR cADMPR = componentCADMPR.getdMPRInterface();
		double period_cadmpr = cADMPR.getPi();
		double theta_cadmpr = 0;
		int m_prime_cadmpr = 0;
		if(cADMPR.getM_prime()*cADMPR.getPi() == cADMPR.getTheta()){
			theta_cadmpr = 0;
			m_prime_cadmpr = cADMPR.getM_prime() + cADMPR.getM_dedicatedCores();
		}else{
			theta_cadmpr = cADMPR.getTheta() - (cADMPR.getM_prime()-1)*cADMPR.getPi(); // partial VCPU's budget
			m_prime_cadmpr = cADMPR.getM_prime() - 1 + cADMPR.getM_dedicatedCores(); 
		}
		edu.penn.rtg.schedulingapp.ResourceModel resourceModel = 
				new edu.penn.rtg.schedulingapp.ResourceModel(period_cadmpr, theta_cadmpr, m_prime_cadmpr,0,0,0);
		resourceModel.setType(type);
		resourceList.addToList(resourceModel);
//		treeComponent.getResourceModelList().addToList(resourceModel);
		
//		treeComponent.setCompName(componentMPR2.getComponentName());
//		treeComponent.getSchCom().setAlgorithm(componentMPR2.getSchedulingPolicy());
		treeComponent.setProcessed(true);
//		treeComponent.setParent(treeComponentParent);
//		treeComponent.setChildren(children);
//		treeComponent.setTaskList(taskList);
		treeComponent.setProcessedTaskList(processedTaskList);
		treeComponent.setResourceModelList(resourceList);
	}
	
	
}
