package edu.penn.rtg.schedulingapp.algo;


import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.ResourceModelList;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.TaskList;
import edu.penn.rtg.schedulingapp.TreeComponent;
import edu.penn.rtg.schedulingapp.util.CartsProgress;
/**
 * SIRAP Resource Model - Abstract Component Interface.
 * <P>
 * A component can be consisted of a set of sub-components or 
 * a set of periodic task. In case of a set of periodic tasks, we can consider 
 * them as a single periodic task which can schedule given periodic tasks. In case 
 * of a set of subcomponents, we can transform each component to single task. Then, 
 * we abstract them as a single task which can schedule all sub-components. 
 * In point of subcomponents, this single task can be considered as resource model 
 * supply certain amount of resouce allocation which is needed to schedule all sub-components.
 * <P>
 * (SIRAP Resource Model)
 *
 * SIRAP Resource Model consist of .... 
 * <P>
 * computed Resource Model using abstract procedure is saved in component c
 * 
 * @author      
 * @version     1.0
 * @since       1.0
 */
public class Sirap{
	CartsProgress cp;
	public void start(TreeComponent comp){
		int size=comp.getChildSize()+2;
		cp=new CartsProgress(size);
		cp.setVisible(true);
	}
	public void end(){
		cp.end();
	}



	/**
	 * Depending on the scheduling algorithm employed by object c, it calculate 
	 * optimal bandwidth by invoking either class EDFSchedulability_periodic or class 
	 * DMSchedulability_periodic. This resource model bandwidth is then used to generate 
	 * the appropriate periodic resource model using one of the constructors of class 
	 * ResourceModel.
	 *
	 * @param  period given period
	 * @param  C	target component
	 * @return      resource model with given period.
	 * @see         ResourceModel
	 */

	protected ResourceModel generateInterface(int period, SchedulingComponent C)
			throws Exception {

		if (C.isDM()) {
			DMSchedulability_sirap schedulability = new DMSchedulability_sirap(
					C, period);
			double bandwidth = schedulability.getBandwidth();
			ResourceModel rm = new ResourceModel(period, bandwidth, period);
			return rm;
		}
		else
		{
			EDFSchedulability_periodic schedulability = new EDFSchedulability_periodic(
					C, period);
			double bandwidth = schedulability.getBandwidth();
			ResourceModel rm = new ResourceModel(period, bandwidth, period);
			return rm;

		}
	}

	/**
	 * Depending on the scheduling algorithm employed by object c, it transform 
	 * given resource model into a task with given period.
	 * @param  edp target resource model
	 * @param  period given period
	 * @param  C	target component
	 * @return      A Task characterizing a periodic task with given period.
	 * @see         Task
	 */
	protected Task transformInterface(ResourceModel rm, int period, SchedulingComponent C)
			throws Exception {
		if (C.isDM()) {
			DMSchedulability_sirap schedulability = new DMSchedulability_sirap(
					C, period);
			return schedulability.T_DM(rm, period);
		}
		else
		{
			EDFSchedulability_periodic schedulability = new EDFSchedulability_periodic(
					C, period);
			return schedulability.T_EDF(rm);
		}
	}

	/**
	 * Abstract them as a single task which can schedule all sub-components.
	 * For each child of c that is also a SchedulingComponent object, the function
	 * iteratively calls itself using the child object as input. When all these iterative
	 * calls return, interfaces have been generated for all the SchedulingComponent
	 * objects which are present in the subtree rooted at c. In particular, for all the
	 * children of c that are SchedulingComponent objects, their ProcessedTaskList
	 * data structure contains the interface tasks. That is, it contains the list of tasks
	 * generated from Periodic resource models (one for each period value in the range
	 * [MinimumPeriod, MaximumPeriod]) that will be presented to c.
	 * <P>
	 * The tasks in the workload of c comprises of all the tasks in the TaskList data
	 * structure as well as specic tasks from the ProcessedTaskList data structure
	 * of its children. 
	 * <P>
	 * Function abstractionProcedure first invokes function generateInterface
	 * and then invokes function transformInterface for each period value i. gen-
	 * erateInterface returns a periodic resource model with period i, which is then
	 * transformed into a periodic task with period i by function transformInter-
	 * face. 
	 * <P>
	 * The resource model is stored in the ResourceModelList data structure
	 * and the transformed task is stored in the ProcessedTaskList data structure
	 * of object c. Further, if c has a parent SchedulingComponent object, then the
	 * tasks in ProcessedTaskList are also copied in the ChildrenToTaskTable
	 * data structure of the parent. Finally, the Processed boolean variable of c is
	 * set to true so that appropriate visual cues can be given in the GUI indicating
	 * that c has been processe
	 * @param  c	Target Component 
	 * @return      none
	 * @see         none
	 */
	public void abstractionProcedure(TreeComponent tc) throws Exception {
		if (tc.getAllChildren().size() != 0) {
			for (TreeComponent comp : tc.getAllChildren()) {
				abstractionProcedure(comp);
			}
		}

		cp.increment();
		SchedulingComponent c=(SchedulingComponent) tc.getSchCom();
		ResourceModelList list = new ResourceModelList();
		TaskList processed = new TaskList();
		//System.out.println(c.getCompName());
		/*
		for (int i = (int) c.getMinPeriod(); i <= (int) c
				.getMaxPeriod(); i++) {
			ResourceModel rm = generateInterface(i, c);
			rm.printDebug();

		}
		*/
		for (int i = (int) c.getMinPeriod(); i <= (int) c
				.getMaxPeriod(); i++) {
			ResourceModel rm = generateInterface(i, c);
			list.getResourceModelArray().add(rm);
			processed.getTasks().add(transformInterface(rm, i, c));
			//rm.printDebug();
		}

		tc.setProcessedTaskList(processed);
		tc.setResourceModelList(list);
		if (tc.hasParentComp()) {
			tc.getParentComp().getChildrenToTaskTable().put(tc, processed);
		}
		
		tc.setProcessed(true);
	}

	public static String check(TreeComponent c) throws Exception {
		if(c.isArincTask())
			return "ARINC"; 
		if(!c.hasCriticalSection())
			return "PRM";
		for (TreeComponent child : c.getAllChildren()) {
			if(!child.getSchCom().isDM()) 
			{
				return "SIRAP task is detected \n but Local scheduler of child component '"+child.getCompName()+"' is not DM";
			}
			if(child.hasChildren()) 
			{
				return "SIRAP task is detected \n but Only 2-Level hierachical scheduling is supported in SIRAP.\nChild component '"
					+child.getCompName()+"' has child components";

			}
		}
		return "SIRAP";

	}


}
