package edu.penn.rtg.schedulingapp.algo;

import java.util.Vector;

import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.ResourceModelList;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.TaskList;
import edu.penn.rtg.schedulingapp.TreeComponent;
import edu.penn.rtg.schedulingapp.basic.PTask;
import edu.penn.rtg.schedulingapp.basic.Workload;
import edu.penn.rtg.schedulingapp.basic.SComponent;
import edu.penn.rtg.schedulingapp.nalgo.EqvPrmAnal;
import edu.penn.rtg.schedulingapp.util.CartsProgress;
import edu.penn.rtg.schedulingapp.util.SchException;
import edu.penn.rtg.schedulingapp.util.UserUtil;

public class EQVPRM {

	TreeComponent startComp;
	CartsProgress cp;
	public EQVPRM(TreeComponent startComp)
	{
		this.startComp=startComp;
	}
	public static boolean check(TreeComponent comp)
	{
		if (comp.getAllChildren().size() != 0) {
			for (TreeComponent c : comp.getAllChildren()) {
				if(!EQVPRM.check(c)) 
					return false;
			}
		}
		if(comp.getSchCom().isEDF())
			return true;
		else
			return false;
	}
	public void run(){
		int size=startComp.getChildSize()+2;
		cp=new CartsProgress(size);
		cp.setVisible(true);
		
		boolean isSchError=false;
		try{
			cp.increment();
			SComponent transCom=tansform(startComp);
			analysis(transCom);
			writeTo(transCom,startComp);
		}
		catch(SchException e){
			isSchError=true;
		}
		catch(Exception e){
			if(!isSchError)
				e.printStackTrace();
		}
		cp.end();
	}

	private SComponent tansform(TreeComponent tc) throws Exception {
		SchedulingComponent c=(SchedulingComponent) tc.getSchCom();

		if (!c.isEDF()) {
			UserUtil.show("Computing EQVPRM interface only works with EDF. Cannot continue");
			throw new Exception();
			
		}
		SComponent midc;
		if (tc.getAllChildren().size() != 0) {
			midc=new SComponent();
			for (TreeComponent comp : tc.getAllChildren()) {
				SComponent tempc=tansform(comp);
				midc.addComp(tempc);
			}
			midc.name=tc.getCompName();
		}
		else
		{
			Workload W=new Workload();
	
			Vector<Task> tasks=c.getMPRTasks();
			for(Task t:tasks) {
				W.addTask((int)t.getPeriod(),t.getExecution(),(int)t.getDeadline());
			}
			//W.display();
			midc=new SComponent(W);
			midc.name=tc.getCompName();
			//System.out.println("N:"+c.getCompName());
			midc.setAlgoEDF();
			midc.setPeriodLimit((int) c.getMaxPeriod());
		}
		return midc;
	}

	private void analysis(SComponent c) {
		EqvPrmAnal.analysis(c);
		EqvPrmAnal.finalizePeriod(c, -1);
		//c.eqvDisplay();
		
	}

	private  void writeTo(SComponent sc, TreeComponent c) {
        Vector<SComponent> comList = sc.getComList();
		if (c.getAllChildren().size() != 0) {
			for (TreeComponent toc : c.getAllChildren()) {
				for(SComponent fromc : comList) {
					//System.out.println("F:"+fromc.name);
					//System.out.println("T:"+toc.getCompName());
					if(fromc.name.equals(toc.getCompName())){
						writeTo(fromc,toc);
						break;
					}
				}
			}
		}
		ResourceModelList list = new ResourceModelList();
		TaskList processed = new TaskList();

		PTask t=sc.getResModel().getTask();
		ResourceModel rm = new ResourceModel(t.period,t.exec,t.deadline);
		rm.setEqvRes(sc.eqvRes);
		rm.setInitRes(sc.initRes);
		rm.type=ResourceModel.EQV;
		list.getResourceModelArray().add(rm);
		processed.getTasks().add(new Task(t.period,t.exec,t.deadline));
		c.setProcessedTaskList(processed);
		c.setResourceModelList(list);
		c.setProcessed(true);
	}

	public static void checkVal(TreeComponent c) {
		if (c.getAllChildren().size() != 0) {
			for (TreeComponent comp : c.getAllChildren()) {
				check(comp);
			}
		}
		System.out.println("ResModel");
		String s=c.getResourceModelList().toString();
		System.out.println(s);
		System.out.println("Task");
		s=c.getProcessedTaskList().toString();
		System.out.println(s);
	}

}
